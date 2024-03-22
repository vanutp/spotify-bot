# What?
An inline Telegram bot to share music tracks you are listening to

# How?
```yaml
services:
  main:
    image: ghcr.io/vanutp/spotify-bot:latest
    restart: always
    environment:
      - 'API_ID=1874'  # https://my.telegram.org -> API development tools
      - 'API_HASH=xxx'  # see above
      - 'BOT_TOKEN=xxx'  # @BotFather
      - 'OWNER_ID=1874'  # e.g. @getmyid_bot
      - 'SPOTIFY_CLIENT_ID=xxx'  # https://developer.spotify.com/dashboard
      - 'SPOTIFY_CLIENT_SECRET=xxx'
      - 'SPOTIFY_REDIRECT_URI=http://localhost:8088'  # must match "Redirect URIs" in spotify dashboard. The actual value doesn't matter
    volumes:
      - ./data:/data
```
