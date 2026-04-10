import os
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI",
    "mongodb+srv://BADMUNDA:BADMYDAD@badhacker.i5nw9na.mongodb.net/")

_client = MongoClient(MONGO_URI)
_db     = _client["music_app"]

plays_col     = _db["plays"]
favs_col      = _db["favorites"]
queue_col     = _db["queue"]
listeners_col = _db["listeners"]
chat_col      = _db["chat_messages"]
users_col     = _db["users"]          # ← for /api/user/<uid>

def init_db():
    plays_col.create_index("user_id")
    favs_col.create_index("user_id")
    chat_col.create_index("room")
    chat_col.create_index("ts")
    users_col.create_index("uid", unique=True)

# ── Plays ──────────────────────────────────────────────────────
def add_play(user_id, song: dict):
    plays_col.insert_one({
        "user_id": user_id,
        "title":   song.get("title", ""),
        "artist":  song.get("artist", ""),
        "audio":   song.get("audio", ""),
        "thumb":   song.get("thumb", "")
    })

# ── Favourites ─────────────────────────────────────────────────
def add_favorite(user_id, song: dict):
    favs_col.insert_one({
        "user_id": user_id,
        "title":   song.get("title", ""),
        "artist":  song.get("artist", ""),
        "audio":   song.get("audio", ""),
        "thumb":   song.get("thumb", "")
    })

def get_user_data(user_id):
    plays = list(plays_col.find({"user_id": user_id}, {"_id": 0}).limit(50))
    favs  = list(favs_col.find({"user_id":  user_id}, {"_id": 0}).limit(50))
    return plays, favs

# ── Queue ──────────────────────────────────────────────────────
def add_queue(song):
    queue_col.insert_one(song)

def get_queue():
    return list(queue_col.find({}, {"_id": 0}))

def pop_next():
    song = queue_col.find_one()
    if song:
        queue_col.delete_one({"_id": song["_id"]})
        del song["_id"]
    return song

# ── Chat ───────────────────────────────────────────────────────
def save_message(room, uid, name, photo, text):
    import datetime
    chat_col.insert_one({
        "room":  room,
        "uid":   uid,
        "name":  name,
        "photo": photo,
        "text":  text,
        "ts":    datetime.datetime.utcnow()
    })

def get_messages(room, limit=80):
    msgs = list(
        chat_col.find({"room": room}, {"_id": 0})
                .sort("ts", -1)
                .limit(limit)
    )
    msgs.reverse()
    return msgs
