import asyncio
import base64
import logging
import time
from urllib.parse import urlencode

import httpx
from httpx import HTTPStatusError
from pydantic import BaseModel

from app.config import config

logger = logging.getLogger(__name__)

spotify_data_file = config.data_dir / 'spotify.json'


class SpotifyData(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    refreshed_at: float | None = None

    @staticmethod
    def load():
        if not spotify_data_file.is_file():
            return SpotifyData()
        return SpotifyData.model_validate_json(spotify_data_file.read_text())

    def save(self):
        spotify_data_file.write_text(self.model_dump_json())


spotify_data = SpotifyData.load()

client = httpx.AsyncClient()

refresh_lock = asyncio.Lock()


def get_auth_url() -> str:
    params = dict(
        response_type='code',
        client_id=config.spotify_client_id,
        scope=' '.join(
            [
                'user-read-recently-played',
                'user-read-playback-position',
                'user-read-playback-state',
                'user-read-currently-playing',
            ]
        ),
        redirect_uri=config.spotify_redirect_uri,
    )
    return 'https://accounts.spotify.com/authorize?' + urlencode(params)


async def process_auth(redirect_url: str):
    code = redirect_url.split('?code=')[1]
    resp = await client.post(
        'https://accounts.spotify.com/api/token',
        data=dict(
            grant_type='authorization_code',
            code=code,
            redirect_uri=config.spotify_redirect_uri,
        ),
        headers={
            'Authorization': 'Basic '
            + base64.b64encode(
                (config.spotify_client_id + ':' + config.spotify_client_secret).encode()
            ).decode()
        },
    )
    resp_json = resp.json()
    try:
        resp.raise_for_status()
    except HTTPStatusError:
        return resp_json
    spotify_data.access_token = resp_json['access_token']
    spotify_data.refresh_token = resp_json['refresh_token']
    spotify_data.refreshed_at = time.time()
    spotify_data.save()


async def refresh_auth():
    async with refresh_lock:
        if time.time() - spotify_data.refreshed_at < 10:
            return
        resp = await client.post(
            'https://accounts.spotify.com/api/token',
            data=dict(
                grant_type='refresh_token',
                refresh_token=spotify_data.refresh_token,
            ),
            headers={
                'Authorization': 'Basic '
                + base64.b64encode(
                    (
                        config.spotify_client_id + ':' + config.spotify_client_secret
                    ).encode()
                ).decode()
            },
        )
        resp.raise_for_status()
        resp_json = resp.json()
        spotify_data.access_token = resp_json['access_token']
        spotify_data.refreshed_at = time.time()
        spotify_data.save()


async def request(url: str, *, refresh_on_401: bool = True):
    resp = await client.get(
        'https://api.spotify.com/v1' + url,
        headers={'Authorization': 'Bearer ' + spotify_data.access_token},
    )
    if resp.status_code == 401 and refresh_on_401:
        await refresh_auth()
        return await request(url, refresh_on_401=False)
    resp.raise_for_status()
    if resp.status_code == 204:
        return None
    else:
        return resp.json()


class Track(BaseModel):
    id: str
    name: str
    artist: str

    def __hash__(self):
        return hash(self.id)


def convert_track(track: dict) -> Track | None:
    if track['type'] != 'track':
        return None
    return Track(
        id=track['id'],
        name=track['name'],
        artist=track['artists'][0]['name'],
    )


async def get_tracks() -> list[Track]:
    current, recent = await asyncio.gather(
        request('/me/player/currently-playing'), request('/me/player/recently-played')
    )
    tracks = []
    if current:
        tracks.append(convert_track(current['item']))
    for item in recent['items']:
        tracks.append(convert_track(item['track']))
    tracks = [x for x in tracks if x]
    tracks = list(dict.fromkeys(tracks))
    return tracks
