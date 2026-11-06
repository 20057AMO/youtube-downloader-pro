<p align="left">
  <img src="static/wb-logo.svg" alt="logo" width="90" />
</p>
# YouTube Downloader Pro


<div dir="rtl">

## تحميل فيديوهات يوتيوب بجودة عالية وواجهة احترافية

تطبيق ويب لتحميل فيديوهات وقوائم تشغيل يوتيوب بواجهة مستخدم مبهرة، مع تتبّع التقدم لحظياً ودعم اللغتين العربية والإنجليزية.

</div>

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.1-green?logo=flask)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red)
![Version](https://img.shields.io/badge/version-2.1.0-brightgreen)

---

## Features / المميزات

- **YouTube video & playlist downloads** — 360p up to 4K when `ffmpeg` is available.
- **MP3 audio extraction** (192 kbps) — requires `ffmpeg`.
- **Real-time progress** — Server-Sent Events (SSE) with an automatic HTTP polling fallback.
- **Organized playlists** — each playlist goes into its own folder; existing folders are never overwritten.
- **Bilingual UI** — Arabic (RTL, default) and English (LTR).
- **Downloads library** — browse files and folders and serve individual files from the browser.
- **Hardened API** — YouTube-only URL allowlist (SSRF protection), optional HTTP Basic Auth, per-IP rate limiting, task caps, path-traversal protection and security headers.
- **Cross-platform** — Docker, Linux, macOS and Windows.
- **Clear ffmpeg diagnostics** — without `ffmpeg` the app still works for older videos that expose progressive MP4 streams; for modern videos it explains in the UI that ffmpeg is required instead of showing a raw yt-dlp error. MP3 always requires ffmpeg.

---

## Requirements / المتطلبات

| Dependency | Notes |
|---|---|
| Python 3.10+ | 3.12 recommended |
| `ffmpeg` + `ffprobe` | Recommended. Needed for merged high-resolution video and MP3 extraction. The Docker image includes it. |
| Docker + Compose | Optional, for containerized deployment |

---

## Quick Start / البدء السريع

### Linux / macOS

```bash
git clone https://github.com/20057AMO/youtube-downloader-pro.git
cd youtube-downloader-pro

./start_linux_mac.sh
```

Or manually:

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Optional but recommended (installs ffmpeg into the venv)
python install_ffmpeg.py

python app.py
```

### Windows

```bat
start_windows.bat
```

Or manually:

```bat
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

REM Optional but recommended
python install_ffmpeg.py

python app.py
```

Open <http://localhost:5000>.

> `python install_ffmpeg.py --check` reports whether `ffmpeg`/`ffprobe` are usable. The installer supports Linux amd64/arm64, macOS (static build, Homebrew fallback) and Windows (gyan.dev build). If automatic installation is not possible, install ffmpeg with your package manager (`apt install ffmpeg`, `brew install ffmpeg`, winget/choco, …).

### Docker

```bash
mkdir -p downloads
cp .env.example .env      # optional, edit as needed
docker compose up -d --build
```

The app is then available on <http://localhost:5000> (override the host port with `PORT` in `.env`).

The container runs as the non-root `appuser`. A root entrypoint fixes ownership of the bind-mounted `./downloads` directory on startup and then drops privileges, so a root-owned host folder no longer causes `Permission denied`.

```bash
docker compose logs -f web
docker compose down
```

---

## Configuration / الإعدادات

All settings are environment variables and are read by the app. With Docker Compose, values from `.env` are forwarded to the container automatically (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Host port used by Docker Compose. The container always listens on 5000. |
| `FLASK_ENV` | `production` | Informational flag. |
| `APP_USERNAME` | *(empty)* | Enables HTTP Basic Auth when set together with `APP_PASSWORD`. |
| `APP_PASSWORD` | *(empty)* | Basic Auth password. |
| `CORS_ORIGINS` | *(empty)* | Comma-separated allowed browser origins. Empty = same-origin only (recommended). |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-IP request limit for `POST /api/info` and `POST /api/download`. |
| `TRUST_PROXY` | `0` | Set to `1` only behind a trusted reverse proxy that sets `X-Forwarded-For`. |
| `MAX_ACTIVE_DOWNLOADS` | `3` | Downloads that run concurrently. |
| `MAX_QUEUED_TASKS` | `20` | Additional downloads that may wait in the queue. |
| `MAX_PLAYLIST_ITEMS` | `500` | Maximum entries returned by `/api/info` (downloads are not truncated). |
| `COOKIES_FILE` | *(empty)* | Netscape-format cookies file passed to yt-dlp (bot-check workaround). |

### Enabling authentication

```bash
APP_USERNAME=admin
APP_PASSWORD=a-strong-password
```

With Docker Compose, put these in `.env`. The UI and every `/api/*` route except `/api/health` will require HTTP Basic Auth; browsers prompt automatically.

### Using YouTube cookies

YouTube may require cookies on server/datacenter IPs. Export a Netscape-format `cookies.txt` and mount it read-only:

```yaml
services:
  web:
    volumes:
      - ./downloads:/app/downloads
      - ./cookies.txt:/app/cookies.txt:ro
    environment:
      - COOKIES_FILE=/app/cookies.txt
```

When running locally, set `COOKIES_FILE=/absolute/path/to/cookies.txt`.

---

## API Reference

All responses are JSON. Errors use the shape `{"error": "..."}` (some routes also include `success`). API responses are sent with `Cache-Control: no-store`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/api/health` | Status, yt-dlp version, ffmpeg availability, auth state, active/queued tasks |
| `POST` | `/api/info` | Fetch video/playlist metadata |
| `POST` | `/api/download` | Create a download task |
| `GET` | `/api/progress/<task_id>` | Task progress as JSON |
| `GET` | `/api/stream/<task_id>` | SSE progress stream (sends `retry: 2000` first, plus heartbeats) |
| `GET` | `/api/downloads` | List downloaded files/folders (`?folder=` for a subfolder) |
| `GET` | `/api/download-file` | Download a file (`?name=…&folder=…`) |
| `POST` | `/api/open-folder` | Open the downloads folder on the host (desktop only; returns `opened: false` when unavailable) |

### Examples

```bash
# Health
curl http://localhost:5000/api/health

# Video / playlist metadata
curl -X POST http://localhost:5000/api/info \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Start a 1080p video download
curl -X POST http://localhost:5000/api/download \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","type":"video","quality":"1080","audio_only":false}'

# Poll progress
curl http://localhost:5000/api/progress/<task_id>

# Stream progress
curl -N http://localhost:5000/api/stream/<task_id>

# With Basic Auth enabled
curl -u admin:password http://localhost:5000/api/downloads
```

**Accepted URLs:** only `http(s)` URLs on YouTube hosts (`youtube.com`, `www.youtube.com`, `m.youtube.com`, `music.youtube.com`, `gaming.youtube.com`, `youtu.be`, `youtube-nocookie.com`, and their `www.` variants). Any other URL is rejected with `400` — this prevents the server from being used as an open download proxy (SSRF).

**Accepted download options:** `type` is `video` or `playlist`; `quality` is one of `best`, `2160`, `1440`, `1080`, `720`, `480`, `360`; `audio_only` must be a JSON boolean (only `true` enables it).

**Limits:** `429` is returned when the per-IP rate limit or the download queue cap is reached (`Retry-After` is set for rate limits).

---

## Project Structure

```
youtube-downloader-pro/
├── app.py                  # Flask API and routes
├── downloader.py           # yt-dlp integration, task registry, progress
├── install_ffmpeg.py       # Cross-platform ffmpeg installer / checker
├── requirements.txt
├── Dockerfile
├── docker-entrypoint.sh    # Fixes volume permissions, then drops to appuser
├── docker-compose.yml
├── start_linux_mac.sh
├── start_windows.bat
├── tests/                  # unittest-suite (no network)
├── static/
│   ├── index.html
│   ├── app.js
│   ├── i18n.js             # Arabic / English translations
│   ├── style.css
│   └── wb-logo.svg
├── downloads/              # Created automatically (user content, git-ignored)
└── .env.example
```

---

## Security Notes

- **SSRF protection** — downloads are restricted to an explicit YouTube host allowlist (no substring checks).
- **Optional Basic Auth** — disabled by default. If you expose the app beyond `localhost`, set `APP_USERNAME` and `APP_PASSWORD` (or put it behind an authenticating reverse proxy).
- **Rate limiting** — per-IP sliding window on the two expensive POST endpoints.
- **Task caps** — bounded concurrency and queue prevent memory/CPU exhaustion.
- **Path traversal** — `downloads` and `download-file` reject paths that resolve outside the downloads directory.
- **Headers** — `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and a CSP compatible with the bundled UI.
- **Cookies** are secrets: mount them read-only and never commit them (`.env` and `cookies.txt` should stay out of git).
- Only download content you have the right to download; you are responsible for complying with YouTube's terms and local law.

---

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `Permission denied` writing to `downloads/` | Docker: the entrypoint fixes bind-mount ownership automatically. For custom `user:` setups, `chown -R <uid>:<gid> downloads`. Local: ensure the current user owns `downloads/`. |
| High resolutions fail / no MP3 | `ffmpeg` is missing. Run `python install_ffmpeg.py --check`, install it, then restart the server (detection is cached per process). Without ffmpeg, most modern videos cannot be saved because YouTube serves audio and video as separate streams that must be merged; the UI reports this explicitly. |
| `No supported JavaScript runtime` warning in the logs | yt-dlp can use a JS runtime to improve YouTube extraction. It is optional: install Deno or a recent Node.js (20+) and add it to `PATH`, then restart. Downloads usually work without it, but some formats may be missing. |
| `Sign in to confirm you're not a bot` | YouTube bot protection. Provide `COOKIES_FILE`, use a residential IP, and keep `yt-dlp` up to date (`pip install -U yt-dlp`). |
| `429` responses | Rate limit or task queue is full. Wait, or raise `RATE_LIMIT_PER_MINUTE` / `MAX_QUEUED_TASKS`. |
| `401 Unauthorized` | Basic Auth is enabled. Provide credentials (`curl -u user:pass`); browsers prompt automatically. |
| Health says `"ffmpeg": false` after installing | Restart the process; ffmpeg detection is cached. |
| Windows installer path issues | Make sure the venv is activated so `venv\Scripts\ffmpeg.exe` is discoverable, or add it to `PATH`. |

---

## Limitations

- Tasks are stored in memory: restarting the process loses task/progress state (downloaded files remain).
- Run a **single worker** (`--workers 1`). The task registry is in-process; multiple workers would not share state.
- Each active SSE stream occupies one server thread. Docker runs 16 worker threads; more than ~16 concurrent streams will queue requests (the UI falls back to polling on stream errors).
- `/api/info` returns at most `MAX_PLAYLIST_ITEMS` playlist entries; the download itself is complete.
- `yt-dlp` changes frequently; pinning is intentionally loose (`>=`) so security/extractor fixes can be installed. Update it if downloads suddenly fail.
- No authentication by default — do not expose the service directly to the internet without setting credentials or a reverse proxy.

---

## Tests

The suite uses the standard library only, mocks all network/yt-dlp calls, and covers validation, auth, rate limiting, task caps, SSE payloads, traversal protection, and the downloader state machine.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

---

## Credits

Built by [Web Builders](https://20057amo.github.io/webbuilders/). Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FFmpeg](https://ffmpeg.org/).
