import base64

from pydantic import BaseModel
from telethon.tl import types

from app.config import config

cache_file = config.data_dir / 'cache.json'


class CachedDocument(BaseModel):
    id: int
    access_hash: int
    file_reference: str

    @staticmethod
    def from_tg(tg_doc: types.InputDocument):
        return CachedDocument(
            id=tg_doc.id,
            access_hash=tg_doc.access_hash,
            file_reference=base64.b64encode(tg_doc.file_reference).decode(),
        )

    def to_tg(self) -> types.InputDocument:
        return types.InputDocument(
            id=self.id,
            access_hash=self.access_hash,
            file_reference=base64.b64decode(self.file_reference),
        )


class Cache(BaseModel):
    inline_docs: dict[str, CachedDocument] = {}
    sent_docs: dict[str, CachedDocument] = {}

    @staticmethod
    def load():
        if not cache_file.is_file():
            return Cache()
        return Cache.model_validate_json(cache_file.read_text())

    def save(self):
        cache_file.write_text(self.model_dump_json())


cache = Cache.load()
