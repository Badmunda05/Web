import os
import aiohttp
import asyncio
from typing import Optional

# ── Bad API (52.77.245.217:8080) ──────────────────────────────
API_BASE = "http://52.77.245.217:8080"

DOWNLOAD_DIR = "static/downloads"

# ── Helpers ───────────────────────────────────────────────────

def extract_video_id(link: str) -> str:
    """Extract YouTube video ID from a URL or return as-is if it's already an ID."""
    if "v=" in link:
        return link.split("v=")[-1].split("&")[0]
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0]
    return link.strip()


# ── Search ────────────────────────────────────────────────────

async def search_songs(query: str, limit: int = 5) -> list:
    """
    GET /search?q=...&limit=5
    Returns list of results: [{id, title, ...}, ...]
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/search",
                params={"q": query, "limit": limit},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                if isinstance(data, dict):
                    return data.get("results", [])
                return data if isinstance(data, list) else []
    except Exception:
        return []


# ── Video Info ────────────────────────────────────────────────

async def get_video_info(video_id: str) -> Optional[dict]:
    """GET /video/info/:id — Returns video metadata dict."""
    vid = extract_video_id(video_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/video/info/{vid}",
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception:
        return None


# ── Audio Stream URL ──────────────────────────────────────────

async def get_audio_url(video_id: str) -> Optional[str]:
    """GET /video/audio/:id — Returns direct audio stream URL."""
    vid = extract_video_id(video_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/video/audio/{vid}",
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if isinstance(data, dict):
                    return data.get("url") or data.get("audio_url") or data.get("link")
                if isinstance(data, str):
                    return data
                return None
    except Exception:
        return None


# ── Video URL (with quality) ──────────────────────────────────

async def get_video_url(video_id: str, quality: str = "720p") -> Optional[str]:
    """GET /video/url/:id?quality=720p — Returns direct video URL."""
    vid = extract_video_id(video_id)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/video/url/{vid}",
                params={"quality": quality},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if isinstance(data, dict):
                    return data.get("url") or data.get("video_url") or data.get("link")
                if isinstance(data, str):
                    return data
                return None
    except Exception:
        return None


# ── Download Song (save to disk) ──────────────────────────────

async def download_song(link: str) -> Optional[str]:
    """
    Download audio and save to static/downloads/<id>.mp3
    Returns local path /downloads/<id>.mp3 on success.
    """
    vid = extract_video_id(link)
    if not vid or len(vid) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{vid}.mp3")

    # Return cached file if already downloaded
    if os.path.exists(file_path):
        return f"/downloads/{vid}.mp3"

    # Get audio URL from Bad API then stream-download it
    audio_url = await get_audio_url(vid)
    if audio_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    audio_url,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status == 200:
                        with open(file_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(16384):
                                f.write(chunk)
                        return f"/downloads/{vid}.mp3"
        except Exception:
            pass

    return None


# ── Stream URL (no download) ──────────────────────────────────

async def get_stream_url(link: str) -> Optional[str]:
    """
    Returns a direct streaming audio URL without saving to disk.
    Uses GET /video/audio/:id endpoint.
    """
    vid = extract_video_id(link)
    if not vid or len(vid) < 3:
        return None
    return await get_audio_url(vid)
