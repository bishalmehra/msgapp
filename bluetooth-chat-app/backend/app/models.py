from datetime import datetime, timezone
from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    bluetoothName: str = Field(min_length=2, max_length=80)
    deviceId: str | None = Field(default=None, max_length=120)


class AuthResponse(BaseModel):
    token: str
    user: dict


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    transport: str = Field(default="cloud")


class MessageOut(BaseModel):
    id: str
    chatId: str
    senderId: str
    text: str
    transport: str
    createdAt: datetime


def normalize_message(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "chatId": doc["chatId"],
        "senderId": doc["senderId"],
        "text": doc["text"],
        "transport": doc.get("transport", "cloud"),
        "createdAt": doc.get("createdAt", datetime.now(timezone.utc)),
    }
