import logging

import aiorun
from telethon import TelegramClient, events, Button, errors
from telethon.tl import types, functions
from telethon.tl.custom import InlineBuilder
from telethon.tl.patched import Message
from telethon.tl.types import UpdateBotInlineSend, DocumentAttributeAudio
from telethon.utils import get_input_document

from app.cache import cache, CachedDocument
from app.config import config
from app.spotify_api import spotify_data, get_auth_url, process_auth, get_tracks, Track
from app.utils import spotify_to_youtube, download_youtube

logging.basicConfig(
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot = TelegramClient(str(config.data_dir / 'bot'), config.api_id, config.api_hash)
bot.parse_mode = 'html'

empty_file: types.TypeInputFile = None

tracks_memcache: dict[str, Track] = {}


async def update_empty_file():
    global empty_file
    empty_file = await bot.upload_file('app/empty.mp3')


async def _get_cached_track(track: Track) -> types.InputBotInlineResultDocument:
    cached_file = cache.inline_docs.get(track.id)
    if cached_file:
        file = cached_file.to_tg()
    else:
        file = empty_file
    res = await InlineBuilder(bot).document(
        file,
        title=track.name,
        description=track.artist,
        id=track.id,
        attributes=[
            DocumentAttributeAudio(
                duration=1,
                voice=False,
                title=track.name,
                performer=track.artist,
                waveform=None,
            )
        ],
        text=get_bottom_bar(track.id),
        buttons=[Button.inline('Loading...', 'loading')],
    )
    if not cached_file:
        cache.inline_docs[track.id] = CachedDocument.from_tg(res.document)
        cache.save()
    return res


async def get_cached_track(track: Track) -> types.InputBotInlineResultDocument:
    try:
        return await _get_cached_track(track)
    except (errors.FilePartMissingError, errors.FilePart0MissingError, TypeError):
        await update_empty_file()
        return await _get_cached_track(track)


@bot.on(events.NewMessage(func=lambda msg: msg.is_private))
async def on_message(msg: Message):
    if msg.sender_id == config.owner_id and not spotify_data.access_token:
        if msg.text.startswith('/start'):
            await msg.respond(get_auth_url())
        else:
            err = await process_auth(msg.text)
            if err:
                await msg.respond(str(err))
            else:
                await msg.respond('ok')
        return
    await msg.respond('meow meow')


def get_bottom_bar(spotify_id: str):
    return f'<a href="https://open.spotify.com/track/{spotify_id}">Spotify</a> | <a href="https://song.link/s/{spotify_id}">Other</a>'


@bot.on(events.InlineQuery())
async def on_inline_query(e: events.InlineQuery.Event):
    if e.sender_id != config.owner_id:
        return await e.answer(
            switch_pm='You are not the bot owner :(', switch_pm_param='meow'
        )
    if not spotify_data.access_token:
        return await e.answer(switch_pm='Login first', switch_pm_param='meow')
    try:
        tracks = await get_tracks()
    except Exception:
        logger.exception('Error loading tracks')
        return await e.answer(switch_pm='Error :(', switch_pm_param='meow')
    tracks = tracks[:5]
    for track in tracks:
        tracks_memcache[track.id] = track

    await e.answer([await get_cached_track(track) for track in tracks])


@bot.on(events.Raw([UpdateBotInlineSend]))
async def feedback(e: UpdateBotInlineSend):
    try:
        track = tracks_memcache[e.id]
        youtube_id = await spotify_to_youtube(e.id)
        py_file, duration = await download_youtube(youtube_id)
        cached_file = cache.sent_docs.get(e.id)
        if cached_file:
            file = cached_file.to_tg()
        else:
            _, media, _ = await bot._file_to_media(
                py_file,
                attributes=[
                    DocumentAttributeAudio(
                        duration=duration,
                        voice=False,
                        title=track.name,
                        performer=track.artist,
                        waveform=None,
                    )
                ],
            )
            uploaded_media = await bot(
                functions.messages.UploadMediaRequest(
                    types.InputPeerSelf(), media=media
                )
            )
            file = get_input_document(uploaded_media.document)
            cache.sent_docs[e.id] = CachedDocument.from_tg(file)
            cache.save()
        await bot.edit_message(e.msg_id, file=file, text=get_bottom_bar(e.id))
    except Exception:
        logger.exception('Error loading track')
        await bot.edit_message(e.msg_id, text='Error :(\n' + get_bottom_bar(e.id))


async def amain():
    await bot.start(bot_token=config.bot_token)
    await update_empty_file()
    logger.info('Bot started')
    await bot.run_until_disconnected()


def main():
    aiorun.run(amain(), stop_on_unhandled_errors=True)
