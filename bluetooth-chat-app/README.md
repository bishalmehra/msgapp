# Bluetooth Chat App (FastAPI + Node Frontend)

This project now follows your requested architecture:
- **Backend**: Python + FastAPI + MongoDB
- **Frontend**: Node.js (serving the client app)

## Project Structure
- `backend/` -> FastAPI backend APIs and websocket chat notifications
- `frontend/` -> Node.js frontend server and static client pages

## Backend Setup (FastAPI)
1. Go to backend:
   - `cd backend`
2. Create virtual env:
   - Windows: `python -m venv .venv && .venv\Scripts\activate`
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Create env:
   - Copy `backend/.env.example` to `backend/.env`
5. Run backend:
   - `uvicorn app.main:app --reload --port 8000`

Backend URL: `http://localhost:8000`

## Frontend Setup (Node.js)
1. From project root:
   - `npm run frontend:install`
2. Start frontend:
   - `npm run frontend:dev`

Frontend URL: `http://localhost:3000`

## Current FastAPI Endpoints
- `GET /health`
- `GET /api/chats/{chat_id}/messages`
- `POST /api/chats/{chat_id}/messages`
- `WS /ws/chats/{chat_id}`

## Next Build Steps
- Add JWT auth (`/auth/signup`, `/auth/login`)
- Add users/chats collections
- Add message read/delivery status
- Connect mobile Bluetooth client for nearby mode
