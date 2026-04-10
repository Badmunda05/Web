import os
import aiohttp
import asyncio
from typing import Optional

YOUR_API_URL = None
FALLBACK_API_URL = "https://shrutibots.site"

async def load_api_url():
    global YOUR_API_URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://pastebin.com/raw/rLsBhAQa",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    content = await response.text()
                    YOUR_API_URL = content.strip()
                else:
                    YOUR_API_URL = FALLBACK_API_URL
    except Exception:
        YOUR_API_URL = FALLBACK_API_URL

async def get_api_url():
    global YOUR_API_URL
    if not YOUR_API_URL:
        await load_api_url()
    return YOUR_API_URL

async def download_song(link: str) -> Optional[str]:
    api_url = await get_api_url()

    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "static/downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path):
        return f"/downloads/{video_id}.mp3"

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio"}
            async with session.get(
                f"{api_url}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                download_token = data.get("download_token")
                if not download_token:
                    return None

                stream_url = f"{api_url}/stream/{video_id}?type=audio"
                async with session.get(
                    stream_url,
                    headers={"X-Download-Token": download_token},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as file_response:
                    if file_response.status != 200:
                        return None
                    with open(file_path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(16384):
                            f.write(chunk)
                    return f"/downloads/{video_id}.mp3"
    except Exception:
        return None

async def get_stream_url(link: str) -> Optional[str]:
    api_url = await get_api_url()
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link

    try:
        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio"}
            async with session.get(
                f"{api_url}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                download_token = data.get("download_token")
                if not download_token:
                    return None
                return f"{api_url}/stream/{video_id}?type=audio&token={download_token}"
    except Exception:
        return None
