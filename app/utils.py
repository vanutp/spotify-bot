import asyncio
import functools
import io
import os.path
from io import BytesIO
from tempfile import TemporaryDirectory

import httpx
from yt_dlp import YoutubeDL

from app import config

client = httpx.AsyncClient(timeout=30)


async def spotify_to_youtube(spotify_id: str) -> str:
    resp = await client.get(
        'https://api.song.link/v1-alpha.1/links',
        params=dict(
            url=f'spotify:track:{spotify_id}',
            songIfSingle='true',
        ),
    )
    resp.raise_for_status()
    return resp.json()['linksByPlatform']['youtube']['entityUniqueId'].split(':')[2]


def _download(youtube_id: str, directory: str):
    params = {
        'format': 'bestaudio',
        'quiet': True,
        'outtmpl': os.path.join(directory, 'dl.%(ext)s'),
    }
    if config.proxy:
        params['proxy'] = config.proxy
    with YoutubeDL(params) as ydl:
        return ydl.extract_info(youtube_id)


async def download_youtube(youtube_id: str) -> tuple[BytesIO, int]:
    with TemporaryDirectory() as tmpdir:
        info = await asyncio.get_event_loop().run_in_executor(
            None, functools.partial(_download, youtube_id, tmpdir)
        )
        duration = info['duration']
        files = os.listdir(tmpdir)
        assert len(files) == 1
        fn = os.path.join(tmpdir, files[0])
        fn2 = os.path.join(tmpdir, 'audio.mp3')
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg',
            '-i',
            fn,
            fn2,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        assert proc.returncode == 0
        with open(fn2, 'rb') as f:
            res = io.BytesIO(f.read())
        res.name = os.path.basename(fn2)
        return res, duration
