from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
from typing import List, Dict, Optional
import os
import time
from downloader import download_song, get_stream_url
from bot import run_bot

# ── In-memory stores ──────────────────────────────────────────
# For production use MongoDB/Redis, but this works perfectly
chat_messages: List[dict] = []          # Global chat history (last 200)
play_history:  Dict[str, List] = {}     # uid -> list of played songs
listeners_meta: Dict[str, dict] = {}    # socket_id -> {uid, name, photo, username}

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_bot())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Music Room ────────────────────────────────────────────────
class MusicRoom:
    def __init__(self):
        self.current_song   = None
        self.is_playing     = False
        self.seek_time      = 0.0
        self.last_update_time = 0.0
        self.listeners: List[WebSocket] = []

    def get_current_seek(self):
        if self.is_playing:
            return self.seek_time + (time.monotonic() - self.last_update_time)
        return self.seek_time

room = MusicRoom()

# ── Helpers ───────────────────────────────────────────────────
def room_state():
    return {
        "type":           "state_update",
        "current_song":   room.current_song,
        "is_playing":     room.is_playing,
        "seek_time":      room.get_current_seek(),
        "listeners":      list(listeners_meta.values()),
        "listeners_count": len(room.listeners),
    }

async def broadcast_state():
    state = room_state()
    dead = []
    for ws in room.listeners:
        try:
            await ws.send_json(state)
        except Exception:
            dead.append(ws)
    for ws in dead:
        room.listeners.remove(ws)

async def broadcast_chat(msg: dict):
    pkt = {"type": "chat_message", **msg}
    dead = []
    for ws in room.listeners:
        try:
            await ws.send_json(pkt)
        except Exception:
            dead.append(ws)
    for ws in dead:
        room.listeners.remove(ws)

# ── REST Endpoints ─────────────────────────────────────────────

@app.get("/status")
async def get_status():
    return room_state()

@app.post("/play_song")
async def play_song(link: str):
    url = await download_song(link)
    if url:
        room.current_song = {
            "title": link.split("/")[-1] if "/" in link else "Song",
            "url":   url,
            "link":  link,
        }
        room.is_playing       = True
        room.seek_time        = 0.0
        room.last_update_time = time.monotonic()
        await broadcast_state()
        return {"status": "success", "url": url}
    return JSONResponse(status_code=400, content={"status": "error", "detail": "Could not download song"})

# ── Profile / History ──────────────────────────────────────────

@app.get("/api/profile/{uid}")
async def get_profile(uid: str):
    history = play_history.get(uid, [])
    # Find user meta from current listeners
    meta = next((v for v in listeners_meta.values() if v.get("uid") == uid), {})
    return {
        "uid":      uid,
        "name":     meta.get("name", "Guest"),
        "username": meta.get("username", ""),
        "photo":    meta.get("photo", ""),
        "plays":    history,
        "play_count": len(history),
    }

@app.post("/api/play_log")
async def log_play(request: Request):
    data = await request.json()
    uid  = str(data.get("uid", "guest"))
    song = data.get("song", {})
    if song and uid:
        history = play_history.setdefault(uid, [])
        history.insert(0, song)
        if len(history) > 50:
            history.pop()
    return {"status": "ok"}

# ── Chat REST (history load) ────────────────────────────────────

@app.get("/api/chat")
async def get_chat():
    return {"messages": chat_messages[-80:]}

@app.post("/api/chat")
async def post_chat(request: Request):
    data = await request.json()
    msg  = {
        "uid":   str(data.get("uid", "guest")),
        "name":  data.get("name", "Guest"),
        "photo": data.get("photo", ""),
        "text":  data.get("text", "").strip(),
        "ts":    int(time.time() * 1000),
    }
    if msg["text"]:
        chat_messages.append(msg)
        if len(chat_messages) > 200:
            chat_messages.pop(0)
        await broadcast_chat(msg)
    return {"status": "ok"}

# ── WebSocket ──────────────────────────────────────────────────

@app.websocket("/ws/{uid}")
async def websocket_endpoint(websocket: WebSocket, uid: str):
    await websocket.accept()
    room.listeners.append(websocket)
    sid = str(id(websocket))

    # Send current state + chat history immediately
    await websocket.send_json({
        **room_state(),
        "chat_history": chat_messages[-40:],
    })

    try:
        while True:
            raw  = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "join":
                # User identifies themselves (Telegram profile)
                listeners_meta[sid] = {
                    "uid":      uid,
                    "name":     data.get("name", "Guest"),
                    "photo":    data.get("photo", ""),
                    "username": data.get("username", ""),
                }
                await broadcast_state()

            elif msg_type == "play":
                room.is_playing       = True
                room.seek_time        = float(data.get("seek_time", room.get_current_seek()))
                room.last_update_time = time.monotonic()
                await broadcast_state()

            elif msg_type == "pause":
                room.is_playing       = False
                room.seek_time        = float(data.get("seek_time", room.get_current_seek()))
                room.last_update_time = time.monotonic()
                await broadcast_state()

            elif msg_type == "seek":
                room.seek_time        = float(data.get("seek_time", 0))
                room.last_update_time = time.monotonic()
                await broadcast_state()

            elif msg_type in ("skip", "stop"):
                room.current_song = None
                room.is_playing   = False
                await broadcast_state()

            elif msg_type == "chat_message":
                text = data.get("text", "").strip()
                if text:
                    meta = listeners_meta.get(sid, {})
                    msg = {
                        "uid":   uid,
                        "name":  meta.get("name", data.get("name", "Guest")),
                        "photo": meta.get("photo", data.get("photo", "")),
                        "text":  text,
                        "ts":    int(time.time() * 1000),
                    }
                    chat_messages.append(msg)
                    if len(chat_messages) > 200:
                        chat_messages.pop(0)
                    await broadcast_chat(msg)

    except WebSocketDisconnect:
        if websocket in room.listeners:
            room.listeners.remove(websocket)
        listeners_meta.pop(sid, None)
        await broadcast_state()

# ── Static (must be LAST) ─────────────────────────────────────
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
