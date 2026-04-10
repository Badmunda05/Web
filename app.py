import os
import requests
import logging
from flask import Flask, request, render_template, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "bad-music-secret-2025")
socketio = SocketIO(app, cors_allowed_origins="*")

db.init_db()

# ── External API Server ───────────────────────────────────────
API_SERVER = os.environ.get("API_SERVER", "http://52.77.245.217:8080")

def api_get(path, params=None):
    r = requests.get(f"{API_SERVER}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# In-memory listeners dict
listeners = {}

# ── Pages ─────────────────────────────────────────────────────

@app.route("/")
def home():
    audio_url = request.args.get("audio", "").strip()
    if not audio_url:
        return render_template("join.html", title="BAD MUSIC")
    title  = request.args.get("title", "Now Playing")
    thumb  = request.args.get("thumb", url_for("static", filename="img/default_album.png"))
    artist = request.args.get("artist", "YouTube")
    return render_template("player.html",
                           audio_url=audio_url,
                           title=title,
                           thumb=thumb,
                           artist=artist)

@app.route("/me")
def me():
    uid = request.args.get("uid", "guest")
    plays, favs = db.get_user_data(uid)
    return render_template("profile.html", uid=uid, plays=plays, favs=favs)

@app.route("/chat")
def chat():
    uid   = request.args.get("uid", "guest")
    room  = request.args.get("room", "global")
    return render_template("chatting.html", uid=uid, room=room)

# ── User API (Telegram profile from DB) ───────────────────────

@app.route("/api/user/<uid>")
def get_user(uid):
    if db.users_col is not None:
        u = db.users_col.find_one({"uid": uid}, {"_id": 0})
        if u:
            u.pop("phone", None)
            return jsonify(u)
    return jsonify({}), 404

# ── Search ────────────────────────────────────────────────────

@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Query required", "results": []}), 400
    try:
        data    = api_get("/search", {"q": q})
        results = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            results = []
        return jsonify({"results": results, "query": q})
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Search server offline", "results": []}), 503
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e), "results": []}), 500

# ── Video API ─────────────────────────────────────────────────

@app.route("/api/video/info/<vid>")
def video_info(vid):
    try:
        return jsonify(api_get(f"/video/info/{vid}"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/video/audio/<vid>")
def video_audio(vid):
    try:
        return jsonify(api_get(f"/video/audio/{vid}"))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/video/url/<vid>")
def video_url(vid):
    quality = request.args.get("quality", "720p")
    try:
        return jsonify(api_get(f"/video/url/{vid}", {"quality": quality}))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Play / Favourite / Queue ──────────────────────────────────

@app.route("/listeners")
def get_listeners():
    return jsonify({"count": len(listeners), "users": list(listeners.values())})

@app.route("/play", methods=["POST"])
def mark_play():
    data = request.get_json() or {}
    uid  = data.get("uid", "guest")
    song = data.get("song", {})
    if song and isinstance(song, dict):
        db.add_play(uid, song)
    return jsonify({"status": "ok"})

@app.route("/favorite", methods=["POST"])
def mark_fav():
    data = request.get_json() or {}
    uid  = data.get("uid", "guest")
    song = data.get("song", {})
    if song and isinstance(song, dict):
        db.add_favorite(uid, song)
    return jsonify({"status": "ok"})

@app.route("/queue")
def get_queue():
    uid = request.args.get("uid", "guest")
    _, favs = db.get_user_data(uid)
    return jsonify(favs)

# ── Chat Messages API ─────────────────────────────────────────

@app.route("/api/chat/messages")
def get_chat_messages():
    room = request.args.get("room", "global")
    msgs = db.get_messages(room)
    return jsonify(msgs)

@app.route("/api/chat/send", methods=["POST"])
def send_chat_message():
    data = request.get_json() or {}
    db.save_message(
        room=data.get("room", "global"),
        uid=data.get("uid", "guest"),
        name=data.get("name", "Guest"),
        photo=data.get("photo", ""),
        text=data.get("text", "").strip()
    )
    return jsonify({"status": "ok"})

# ── Socket.IO ─────────────────────────────────────────────────

@socketio.on("join")
def handle_join(data):
    uid   = str(data.get("uid", "guest"))
    name  = data.get("name", "Unknown")
    photo = data.get("photo", "")
    listeners[uid] = {"name": name, "photo": photo, "uid": uid}
    emit("user_joined", {"uid": uid, "name": name, "photo": photo}, broadcast=True)

@socketio.on("leave")
def handle_leave(data):
    uid = str(data.get("uid", ""))
    if uid in listeners:
        listeners.pop(uid)
        emit("user_left", {"uid": uid}, broadcast=True)

@socketio.on("chat_message")
def handle_chat(data):
    """Broadcast chat message to room"""
    room  = data.get("room", "global")
    msg   = {
        "uid":   str(data.get("uid", "guest")),
        "name":  data.get("name", "Guest"),
        "photo": data.get("photo", ""),
        "text":  data.get("text", "").strip(),
        "room":  room
    }
    if msg["text"]:
        db.save_message(**{k: msg[k] for k in ["room","uid","name","photo","text"]})
        emit("new_message", msg, broadcast=True)

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5050))
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False)
