"""
YouTube Downloader - Flask Backend Server
"""

from flask import Flask, jsonify, request, send_from_directory, send_file, Response
import base64
import hmac
import json
import os
import platform
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

try:
    from flask_cors import CORS
except ImportError:  # CORS is optional; the app still runs without it.
    CORS = None

from downloader import (
    DOWNLOADS_DIR,
    TaskLimitExceeded,
    create_task,
    ffmpeg_available,
    get_stats,
    get_task,
    get_video_info,
    start_download,
)

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024

ALLOWED_YOUTUBE_HOSTS = frozenset({
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'music.youtube.com',
    'gaming.youtube.com',
    'youtu.be',
    'www.youtu.be',
    'youtube-nocookie.com',
    'www.youtube-nocookie.com',
})
VALID_DOWNLOAD_TYPES = ('video', 'playlist')
VALID_QUALITIES = frozenset({'best', '2160', '1440', '1080', '720', '480', '360'})
RATE_LIMITED_PATHS = ('/api/info', '/api/download')
RATE_LIMIT_WINDOW_SECONDS = 60.0
CSP_POLICY = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "frame-ancestors 'self'"
)

_cors_origins = [
    origin.strip()
    for origin in os.environ.get('CORS_ORIGINS', '').split(',')
    if origin.strip()
]
if CORS is not None and _cors_origins:
    CORS(app, origins=_cors_origins)

_rate_limit_lock = threading.Lock()
_rate_limit_buckets = {}
_last_rate_prune = 0.0


def _env_int(name: str, default: int) -> int:
    """Read a positive integer environment variable, falling back to default."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= 1 else default


def is_youtube_url(url: str) -> bool:
    """Return True only for http(s) URLs on an explicit YouTube host allowlist."""
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
    except ValueError:
        return False
    if parts.scheme.lower() not in ('http', 'https'):
        return False
    if not hostname:
        return False
    normalized = hostname.lower().rstrip('.')
    return normalized in ALLOWED_YOUTUBE_HOSTS


def _auth_credentials():
    """Return configured (username, password), or (None, None) when disabled."""
    username = os.environ.get('APP_USERNAME', '')
    password = os.environ.get('APP_PASSWORD', '')
    if not username or not password:
        return None, None
    return username, password


def _auth_is_enabled() -> bool:
    username, password = _auth_credentials()
    return bool(username and password)


def _valid_basic_auth(header: str, username: str, password: str) -> bool:
    """Validate an HTTP Basic Authorization header using constant-time compares."""
    if not header or not header.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        return False
    supplied_user, separator, supplied_password = decoded.partition(':')
    if not separator:
        return False
    user_ok = hmac.compare_digest(supplied_user.encode(), username.encode())
    password_ok = hmac.compare_digest(supplied_password.encode(), password.encode())
    return user_ok and password_ok


def _trust_proxy() -> bool:
    """Only trust X-Forwarded-For when explicitly enabled behind a proxy."""
    return os.environ.get('TRUST_PROXY', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _client_ip() -> str:
    """Resolve the client IP, honouring X-Forwarded-For only when trusted."""
    if _trust_proxy():
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            first_hop = forwarded.split(',')[0].strip()
            if first_hop:
                return first_hop
    return request.remote_addr or 'unknown'


def _prune_rate_buckets(now: float) -> None:
    """Drop stale IP buckets periodically so the map cannot grow forever."""
    global _last_rate_prune
    if now - _last_rate_prune < RATE_LIMIT_WINDOW_SECONDS:
        return
    stale = [
        ip for ip, bucket in _rate_limit_buckets.items()
        if not bucket or now - bucket[-1] >= RATE_LIMIT_WINDOW_SECONDS
    ]
    for ip in stale:
        _rate_limit_buckets.pop(ip, None)
    _last_rate_prune = now


def _rate_limit_retry_after(ip: str) -> int:
    """Record a hit and return Retry-After seconds, or 0 when allowed."""
    limit = _env_int('RATE_LIMIT_PER_MINUTE', 60)
    now = time.monotonic()
    with _rate_limit_lock:
        _prune_rate_buckets(now)
        bucket = _rate_limit_buckets.setdefault(ip, deque())
        while bucket and now - bucket[0] >= RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            return max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - bucket[0])) + 1)
        bucket.append(now)
        return 0


def _ytdlp_version() -> str:
    """Return the installed yt-dlp version, or 'unknown'."""
    try:
        import yt_dlp
        return getattr(yt_dlp.version, '__version__', None) or 'unknown'
    except Exception:
        return 'unknown'


@app.before_request
def require_basic_auth():
    """Enforce HTTP Basic Auth when both credentials are configured."""
    if request.path == '/api/health':
        return None
    username, password = _auth_credentials()
    if not username or not password:
        return None
    if _valid_basic_auth(request.headers.get('Authorization', ''), username, password):
        return None
    return Response(
        'Unauthorized',
        401,
        {'WWW-Authenticate': 'Basic realm="YouTube Downloader"'},
    )


@app.before_request
def enforce_rate_limit():
    """Apply a per-IP sliding-window limit to expensive POST endpoints."""
    if request.method != 'POST' or request.path not in RATE_LIMITED_PATHS:
        return None
    retry_after = _rate_limit_retry_after(_client_ip())
    if retry_after:
        return jsonify({
            'error': 'تم تجاوز الحد المسموح من الطلبات. حاول مرة أخرى لاحقاً.'
        }), 429, {'Retry-After': str(retry_after)}
    return None


@app.after_request
def set_security_headers(response):
    """Attach hardening headers and disable caching for API responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = CSP_POLICY
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(413)
def handle_payload_too_large(error):
    """Return the standard JSON error shape for oversized request bodies."""
    return jsonify({'error': 'حجم الطلب كبير جداً'}), 413


@app.errorhandler(500)
def handle_internal_error(error):
    """Keep unexpected failures in the JSON error contract."""
    app.logger.exception('Unhandled server error')
    return jsonify({'error': 'حدث خطأ غير متوقع في الخادم'}), 500


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/health')
def api_health():
    stats = get_stats()
    return jsonify({
        'status': 'ok',
        'version': '2.1.0',
        'ytdlp': _ytdlp_version(),
        'ffmpeg': ffmpeg_available(),
        'auth': _auth_is_enabled(),
        'active': stats['active'],
        'queued': stats['queued'],
    })


@app.route('/api/info', methods=['POST'])
def api_info():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'error': 'الرجاء إدخال بيانات صحيحة'}), 400

    url = data.get('url')
    if not isinstance(url, str):
        url = ''
    url = url.strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط صحيح'}), 400

    if not is_youtube_url(url):
        return jsonify({'error': 'الرجاء إدخال رابط يوتيوب صحيح'}), 400

    try:
        info = get_video_info(url)
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        app.logger.exception('Failed to fetch video info for %s', url)
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'error': 'الرجاء إدخال بيانات صحيحة'}), 400

    url = data.get('url')
    if not isinstance(url, str):
        url = ''
    url = url.strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط صحيح'}), 400

    if not is_youtube_url(url):
        return jsonify({'error': 'الرجاء إدخال رابط يوتيوب صحيح'}), 400

    download_type = data.get('type', 'video')
    if download_type not in VALID_DOWNLOAD_TYPES:
        return jsonify({'error': 'نوع التحميل غير صحيح'}), 400

    quality = data.get('quality', 'best')
    if not isinstance(quality, str) or quality not in VALID_QUALITIES:
        return jsonify({'error': 'جودة التحميل غير صحيحة'}), 400

    audio_only = data.get('audio_only') is True

    try:
        task_id = create_task(url, download_type, quality, audio_only)
        start_download(task_id)
    except TaskLimitExceeded:
        return jsonify({
            'error': 'تم الوصول إلى الحد الأقصى لعدد مهام التحميل. حاول مرة أخرى لاحقاً.'
        }), 429
    except Exception:
        app.logger.exception('Failed to start download task')
        return jsonify({'error': 'تعذر بدء مهمة التحميل. حاول مرة أخرى.'}), 500

    return jsonify({'success': True, 'task_id': task_id})


@app.route('/api/progress/<task_id>', methods=['GET'])
def api_progress(task_id):
    task = get_task(task_id)
    if not task:
        return jsonify({'error': 'المهمة غير موجودة'}), 404

    return jsonify({
        'id': task.get('id'),
        'status': task.get('status'),
        'progress': task.get('progress', 0),
        'total': task.get('total', 0),
        'current_item': task.get('current_item', 0),
        'message': task.get('message', ''),
        'items': task.get('items', []),
        'errors': task.get('errors', []),
        'download_path': task.get('download_path', ''),
        'type': task.get('type', 'video'),
    })


@app.route('/api/stream/<task_id>')
def api_stream(task_id):
    if not get_task(task_id):
        return jsonify({'error': 'المهمة غير موجودة'}), 404

    def generate():
        yield 'retry: 2000\n\n'
        started = time.monotonic()
        last_payload = None
        last_sent = started

        while time.monotonic() - started < 3600:
            task = get_task(task_id)
            if not task:
                yield f"data: {json.dumps({'error': 'المهمة غير موجودة'}, ensure_ascii=False)}\n\n"
                break

            payload = {
                'type': task.get('type'),
                'status': task.get('status'),
                'progress': task.get('progress', 0),
                'total': task.get('total', 0),
                'current_item': task.get('current_item', 0),
                'message': task.get('message', ''),
                'items': task.get('items', []),
                'errors': task.get('errors', []),
            }
            serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            now = time.monotonic()

            if serialized != last_payload:
                yield f"data: {serialized}\n\n"
                last_payload = serialized
                last_sent = now
            elif now - last_sent >= 15:
                yield ': ping\n\n'
                last_sent = now

            if task.get('status') in ('completed', 'error'):
                break

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'X-Accel-Buffering': 'no'
                    })


@app.route('/api/downloads', methods=['GET'])
def api_downloads():
    subfolder = request.args.get('folder', '')
    target_dir = DOWNLOADS_DIR
    if subfolder:
        target_dir = DOWNLOADS_DIR / subfolder
        # Prevent path traversal
        try:
            target_dir.resolve().relative_to(DOWNLOADS_DIR.resolve())
        except (ValueError, OSError):
            return jsonify({'error': 'مسار غير صالح'}), 400

    files = []
    if target_dir.exists():
        for item in target_dir.iterdir():
            if item.name.startswith('.'):
                continue
            if item.is_file():
                stat = item.stat()
                files.append({
                    'name': item.name,
                    'size': stat.st_size,
                    'type': 'file',
                    'modified': stat.st_mtime
                })
            elif item.is_dir():
                count = len([
                    child for child in item.iterdir()
                    if child.is_file() and not child.name.startswith('.')
                ])
                files.append({
                    'name': item.name,
                    'count': count,
                    'type': 'folder'
                })

    files.sort(key=lambda x: x.get('modified', 0), reverse=True)
    return jsonify({'files': files, 'folder': subfolder})


@app.route('/api/download-file')
def api_download_file():
    """Serve a file from the downloads directory to the browser."""
    filename = request.args.get('name', '')
    folder = request.args.get('folder', '')

    if not filename:
        return jsonify({'error': 'اسم الملف مطلوب'}), 400

    if Path(filename).name != filename or filename in ('.', '..'):
        return jsonify({'error': 'مسار غير صالح'}), 400

    if folder:
        target_dir = DOWNLOADS_DIR / folder
    else:
        target_dir = DOWNLOADS_DIR

    file_path = target_dir / filename

    # Prevent path traversal
    try:
        file_path.resolve().relative_to(DOWNLOADS_DIR.resolve())
    except (ValueError, OSError):
        return jsonify({'error': 'مسار غير صالح'}), 400

    if not file_path.exists() or not file_path.is_file():
        return jsonify({'error': 'الملف غير موجود'}), 404

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    try:
        if not DOWNLOADS_DIR.exists():
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

        system = platform.system()
        opened = False
        if system == "Windows":
            subprocess.Popen(f'explorer "{DOWNLOADS_DIR}"', shell=True)
            opened = True
        elif system == "Darwin":
            subprocess.Popen(['open', str(DOWNLOADS_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            opened = True
        else:
            # Check if running in a graphical environment
            display = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')
            if display:
                subprocess.Popen(['xdg-open', str(DOWNLOADS_DIR)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                opened = True

        return jsonify({
            'success': True,
            'opened': opened,
            'path': str(DOWNLOADS_DIR)
        })
    except Exception as e:
        app.logger.exception('Failed to open downloads folder')
        return jsonify({
            'success': False,
            'opened': False,
            'path': str(DOWNLOADS_DIR),
            'error': str(e)
        })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  YouTube Downloader Server v2.1.0")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
