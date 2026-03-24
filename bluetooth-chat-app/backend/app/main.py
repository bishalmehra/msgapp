import os
import secrets
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Set

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Header,
    Depends,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware

from .db import mongo, connect_db, close_db
from .models import AuthRequest, MessageCreate, normalize_message

load_dotenv()

app = FastAPI(title="Bluetooth Chat Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CLIENT_ORIGIN", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_connections: Dict[str, Set[WebSocket]] = defaultdict(set)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(dt: datetime | None) -> bool:
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < utc_now()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token.")
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    session = mongo.db.sessions.find_one({"token": token}) if mongo.db is not None else None
    if not session:
        raise HTTPException(status_code=401, detail="Session not found.")
    if _is_expired(session.get("expiresAt")):
        raise HTTPException(status_code=401, detail="Session expired.")

    user = mongo.db.users.find_one({"_id": session["userId"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


@app.on_event("startup")
def startup_event() -> None:
    connect_db()
    mongo.db.users.create_index("bluetoothNameLower", unique=True)
    mongo.db.sessions.create_index("token", unique=True)
    mongo.db.sessions.create_index("expiresAt")
    mongo.db.messages.create_index([("chatId", 1), ("createdAt", 1)])


@app.on_event("shutdown")
def shutdown_event() -> None:
    close_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "bluetooth-chat-fastapi-backend"}


@app.post("/api/auth/register")
def register(payload: AuthRequest) -> dict:
    bluetooth_name = payload.bluetoothName.strip()
    name_lower = bluetooth_name.lower()
    existing = mongo.db.users.find_one({"bluetoothNameLower": name_lower})
    if existing:
        raise HTTPException(status_code=409, detail="Bluetooth name already registered.")

    user_doc = {
        "bluetoothName": bluetooth_name,
        "bluetoothNameLower": name_lower,
        "deviceId": payload.deviceId,
        "createdAt": utc_now(),
    }
    result = mongo.db.users.insert_one(user_doc)
    user_id = result.inserted_id
    token = secrets.token_urlsafe(32)
    session_doc = {
        "token": token,
        "userId": user_id,
        "createdAt": utc_now(),
        "expiresAt": utc_now().replace(microsecond=0),
    }
    # 7-day default auth session
    session_doc["expiresAt"] = session_doc["createdAt"].replace(microsecond=0)
    session_doc["expiresAt"] = datetime.fromtimestamp(
        session_doc["createdAt"].timestamp() + 7 * 24 * 3600, tz=timezone.utc
    )
    mongo.db.sessions.insert_one(session_doc)

    return {
        "token": token,
        "user": {
            "id": str(user_id),
            "bluetoothName": user_doc["bluetoothName"],
            "deviceId": user_doc.get("deviceId"),
        },
    }


@app.post("/api/auth/login")
def login(payload: AuthRequest) -> dict:
    bluetooth_name = payload.bluetoothName.strip().lower()
    user = mongo.db.users.find_one({"bluetoothNameLower": bluetooth_name})
    if not user:
        raise HTTPException(status_code=404, detail="Bluetooth name not registered.")

    token = secrets.token_urlsafe(32)
    now = utc_now()
    mongo.db.sessions.insert_one(
        {
            "token": token,
            "userId": user["_id"],
            "createdAt": now,
            "expiresAt": datetime.fromtimestamp(now.timestamp() + 7 * 24 * 3600, tz=timezone.utc),
        }
    )

    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "bluetoothName": user["bluetoothName"],
            "deviceId": user.get("deviceId"),
        },
    }


@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: str, user: dict = Depends(get_current_user)) -> dict:
    docs = (
        mongo.db.messages.find({"chatId": chat_id}).sort("createdAt", 1)
        if mongo.db is not None
        else []
    )
    messages = [normalize_message(doc) for doc in docs]
    return {
        "chatId": chat_id,
        "count": len(messages),
        "messages": messages,
        "viewerBluetoothName": user["bluetoothName"],
    }


@app.post("/api/chats/{chat_id}/messages", status_code=201)
async def create_message(
    chat_id: str, payload: MessageCreate, user: dict = Depends(get_current_user)
) -> dict:
    if payload.transport not in {"bluetooth", "cloud", "hybrid"}:
        raise HTTPException(status_code=400, detail="Invalid transport type.")

    message = {
        "chatId": chat_id,
        "senderId": str(user["_id"]),
        "senderBluetoothName": user["bluetoothName"],
        "text": payload.text,
        "transport": payload.transport,
        "createdAt": utc_now(),
    }

    result = mongo.db.messages.insert_one(message)
    message["_id"] = result.inserted_id
    normalized = normalize_message(message)

    # Notify all websocket clients in this chat room.
    dead_connections: Set[WebSocket] = set()
    for ws in chat_connections[chat_id]:
        try:
            await ws.send_json({"event": "new_message", "data": normalized})
        except Exception:
            dead_connections.add(ws)

    for ws in dead_connections:
        chat_connections[chat_id].discard(ws)

    return normalized


@app.websocket("/ws/chats/{chat_id}")
async def chat_ws(websocket: WebSocket, chat_id: str, token: str = Query(default="")):
    session = mongo.db.sessions.find_one({"token": token}) if mongo.db is not None else None
    if not session or _is_expired(session.get("expiresAt")):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    chat_connections[chat_id].add(websocket)
    try:
        await websocket.send_json({"event": "joined_chat", "data": {"chatId": chat_id}})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chat_connections[chat_id].discard(websocket)
