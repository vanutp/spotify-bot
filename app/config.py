from pathlib import Path

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    api_id: int
    api_hash: str
    bot_token: str
    owner_id: int
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    data_dir: Path = 'data'


config = Config(_env_file='.env')

config.data_dir.mkdir(parents=True, exist_ok=True)
