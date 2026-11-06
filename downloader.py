"""
YouTube Downloader - Core Download Logic
Uses yt-dlp for reliable downloading.
"""

import os
import re
import sys
import uuid
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Read a positive integer environment variable, falling back to default."""
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


MAX_ACTIVE_DOWNLOADS = _env_int('MAX_ACTIVE_DOWNLOADS', 3)
MAX_QUEUED_TASKS = _env_int('MAX_QUEUED_TASKS', 20, minimum=0)
MAX_PLAYLIST_ITEMS = _env_int('MAX_PLAYLIST_ITEMS', 500)

DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_ACTIVE_DOWNLOADS)
download_tasks = {}
download_tasks_lock = threading.Lock()
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

TASK_MAX_AGE = 3600
_WINDOWS_RESERVED_NAMES = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'}
    | {f'COM{i}' for i in range(1, 10)}
    | {f'LPT{i}' for i in range(1, 10)}
)

_active_downloads = 0
_queued_downloads = 0

_ffmpeg_path_cache = None
_ffmpeg_checked = False
_ffmpeg_lock = threading.Lock()


class TaskLimitExceeded(Exception):
    """Raised when the active/queued download capacity is exhausted."""


def _now_iso() -> str:
    """Return the current local timestamp in ISO format."""
    return datetime.now().isoformat()


def _cleanup_old_tasks() -> None:
    """Drop terminal tasks older than TASK_MAX_AGE."""
    now = datetime.now().timestamp()
    with download_tasks_lock:
        for task_id, task in list(download_tasks.items()):
            if task.get('status') not in ('completed', 'error'):
                continue
            stamp = task.get('finished_at') or task.get('created_at')
            try:
                age = now - datetime.fromisoformat(stamp).timestamp()
            except (TypeError, ValueError):
                age = TASK_MAX_AGE + 1
            if age > TASK_MAX_AGE:
                download_tasks.pop(task_id, None)


def sanitize_filename(filename: str) -> str:
    """Make a string safe to use as a single file/directory name."""
    text = filename if isinstance(filename, str) else str(filename or '')
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    text = text.strip('. ')
    text = text[:150]
    text = text.strip('. ')
    if not text:
        return 'download'
    if text.split('.')[0].upper() in _WINDOWS_RESERVED_NAMES:
        text = f'_{text}'
    return text


def _create_unique_dir(base: Path) -> Path:
    """Atomically create base, or 'name (2)', 'name (3)', ... if it exists."""
    for index in range(1, 1000):
        candidate = base if index == 1 else base.with_name(f'{base.name} ({index})')
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError('تعذر إنشاء مجلد فريد لقائمة التشغيل')


def find_ffmpeg() -> Optional[str]:
    """Locate ffmpeg, checking PATH and the Python executable's directory."""
    global _ffmpeg_path_cache, _ffmpeg_checked
    with _ffmpeg_lock:
        if _ffmpeg_checked:
            return _ffmpeg_path_cache

        candidates = [shutil.which('ffmpeg')]
        exe_dir = os.path.dirname(sys.executable)
        names = ['ffmpeg.exe', 'ffmpeg'] if os.name == 'nt' else ['ffmpeg']
        candidates.extend(os.path.join(exe_dir, name) for name in names)

        _ffmpeg_path_cache = next(
            (path for path in candidates if path and os.path.isfile(path)),
            None,
        )
        _ffmpeg_checked = True
        return _ffmpeg_path_cache


def ffmpeg_available() -> bool:
    """Return True when a usable ffmpeg binary can be found."""
    return find_ffmpeg() is not None


def get_stats() -> dict:
    """Return a snapshot of active and queued download counts."""
    with download_tasks_lock:
        return {'active': _active_downloads, 'queued': _queued_downloads}


def get_task(task_id: str) -> dict:
    """Return a detached copy of a task so callers cannot mutate live state."""
    with download_tasks_lock:
        task = download_tasks.get(task_id)
        if task is None:
            return {}
        copied = dict(task)
        copied['items'] = [
            dict(item) for item in task.get('items', []) if isinstance(item, dict)
        ]
        copied['errors'] = list(task.get('errors', []))
        return copied


def create_task(url: str, download_type: str, quality: str, audio_only: bool) -> str:
    """Create a task and reserve a queue slot, raising when capacity is full."""
    global _queued_downloads

    _cleanup_old_tasks()
    with download_tasks_lock:
        if _active_downloads + _queued_downloads >= MAX_ACTIVE_DOWNLOADS + MAX_QUEUED_TASKS:
            raise TaskLimitExceeded(
                'تم الوصول إلى الحد الأقصى لعدد مهام التحميل. حاول مرة أخرى لاحقاً.'
            )

        task_id = str(uuid.uuid4())
        download_tasks[task_id] = {
            "id": task_id,
            "url": url,
            "type": download_type,
            "quality": quality,
            "audio_only": audio_only,
            "status": "pending",
            "progress": 0,
            "total": 0,
            "current_item": 0,
            "message": "جاري التحضير...",
            "items": [],
            "errors": [],
            "created_at": _now_iso(),
            "download_path": str(DOWNLOADS_DIR)
        }
        _queued_downloads += 1
        return task_id


def get_video_info(url: str) -> dict:
    """Fetch video/playlist info using yt-dlp."""
    try:
        import yt_dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}

            if info.get('_type') == 'playlist':
                entries = info.get('entries') or []
                playlist_count = info.get('playlist_count')
                if playlist_count is None:
                    playlist_count = len(entries)
                visible_entries = entries[:MAX_PLAYLIST_ITEMS]
                thumbnail = info.get('thumbnail') or next(
                    (entry.get('thumbnail') for entry in visible_entries
                     if entry and entry.get('thumbnail')),
                    None,
                )
                return {
                    "type": "playlist",
                    "title": info.get('title') or 'Unknown Playlist',
                    "uploader": info.get('uploader') or 'Unknown',
                    "count": playlist_count,
                    "thumbnail": thumbnail,
                    "items": [
                        {
                            "title": entry.get('title') or f'Video {i+1}',
                            "url": entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                            "duration": entry.get('duration'),
                            "thumbnail": entry.get('thumbnail'),
                        }
                        for i, entry in enumerate(visible_entries) if entry
                    ],
                    "url": url,
                }

            formats = info.get('formats', [])
            available_qualities = set()
            for fmt in formats:
                height = fmt.get('height')
                if height and fmt.get('vcodec') != 'none':
                    available_qualities.add(height)

            return {
                "type": "video",
                "title": info.get('title') or 'Unknown Video',
                "uploader": info.get('uploader') or 'Unknown',
                "duration": info.get('duration'),
                "thumbnail": info.get('thumbnail'),
                "description": (info.get('description') or '')[:300],
                "view_count": info.get('view_count', 0),
                "available_qualities": sorted(list(available_qualities), reverse=True),
                "url": url
            }
    except Exception as e:
        raise Exception(f"فشل في جلب المعلومات: {str(e)}")


def _build_ydl_opts(task: dict, progress_hook, output_template: str) -> dict:
    """Build yt-dlp options for one task, respecting ffmpeg availability."""
    quality = task.get('quality', 'best')
    audio_only = task.get('audio_only', False)
    ffmpeg_path = find_ffmpeg()

    if audio_only:
        if not ffmpeg_path:
            raise RuntimeError(
                'ffmpeg غير مثبّت لتحويل الصوت. ثبّت ffmpeg ثم أعد المحاولة.'
            )
        format_str = 'bestaudio/best'
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        quality_map = {
            'best': 'best',
            '2160': '2160',
            '1440': '1440',
            '1080': '1080',
            '720': '720',
            '480': '480',
            '360': '360',
        }
        selected_quality = quality_map.get(quality) if isinstance(quality, str) else None
        if selected_quality is None:
            raise ValueError('جودة التحميل غير صحيحة')

        if not ffmpeg_path:
            format_str = 'best[ext=mp4]/best'
        elif selected_quality == 'best':
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        else:
            format_str = (
                f'bestvideo[height<={selected_quality}][ext=mp4]+bestaudio[ext=m4a]'
                f'/bestvideo[height<={selected_quality}]+bestaudio/best'
            )
        postprocessors = []

    opts = {
        'format': format_str,
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'retries': 3,
        'fragment_retries': 3,
        'socket_timeout': 30,
    }

    cookies_file = os.environ.get('COOKIES_FILE')
    if cookies_file and os.path.isfile(cookies_file):
        opts['cookiefile'] = cookies_file

    if not audio_only and ffmpeg_path:
        opts['merge_output_format'] = 'mp4'

    if audio_only:
        opts['postprocessors'] = postprocessors

    if ffmpeg_path:
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        opts['ffmpeg_location'] = ffmpeg_dir or ffmpeg_path

    return opts


def _friendly_error(exc: Exception) -> str:
    """Translate the most common yt-dlp failure into actionable Arabic advice."""
    message = str(exc)
    lowered = message.lower()
    if not ffmpeg_available() and (
        'requested format is not available' in lowered
        or 'requested merging of multiple formats' in lowered
    ):
        return (
            'هذا الفيديو يتوفّر كمسارات صوت وفيديو منفصلة، ودمجها يحتاج ffmpeg. '
            'ثبّت ffmpeg (python install_ffmpeg.py) ثم أعد المحاولة.'
        )
    return message


def _format_speed(speed: Optional[float]) -> str:
    """Format a bytes/second rate for the Arabic progress message."""
    if not speed:
        return ''
    if speed > 1024 * 1024:
        return f"{speed / (1024 * 1024):.1f} MB/s"
    return f"{speed / 1024:.0f} KB/s"


def download_single_video(task_id: str, url: str = None):
    """Download a single video."""
    import yt_dlp

    with download_tasks_lock:
        task = download_tasks.get(task_id)
    if task is None:
        return

    target_url = url or task.get('url')

    try:
        output_template = str(DOWNLOADS_DIR / '%(title)s.%(ext)s')

        def progress_hook(d):
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                speed_str = _format_speed(d.get('speed'))
                eta = d.get('eta')
                eta_str = f" | ETA: {eta}s" if eta else ''
                pct = int(downloaded / total * 100) if total > 0 else 0

                with download_tasks_lock:
                    task['progress'] = pct
                    task['message'] = f"جاري التحميل... {pct}% | {speed_str}{eta_str}"
                    task['status'] = 'downloading'

            elif status == 'finished':
                with download_tasks_lock:
                    task['message'] = "جاري المعالجة..."
                    task['progress'] = 99

        ydl_opts = _build_ydl_opts(task, progress_hook, output_template)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])

        with download_tasks_lock:
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = 'تم التحميل بنجاح! ✅'
            task['finished_at'] = _now_iso()

    except Exception as e:
        friendly = _friendly_error(e)
        with download_tasks_lock:
            task['status'] = 'error'
            task['message'] = f'خطأ: {friendly}'
            task['errors'].append(friendly)
            task['finished_at'] = _now_iso()


def download_playlist(task_id: str):
    """Download entire playlist."""
    import yt_dlp

    with download_tasks_lock:
        task = download_tasks.get(task_id)
    if task is None:
        return

    url = task.get('url')

    try:
        with download_tasks_lock:
            task['message'] = "جاري جلب معلومات الـ Playlist..."
            task['status'] = 'fetching'

        ydl_info_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}

        if info.get('_type') == 'playlist':
            entries = [entry for entry in (info.get('entries') or []) if entry]
            playlist_title = sanitize_filename(info.get('title') or 'playlist')
        else:
            entries = [info]
            playlist_title = sanitize_filename(info.get('title') or 'video')

        if task.get('audio_only') and not ffmpeg_available():
            raise RuntimeError(
                'ffmpeg غير مثبّت لتحويل الصوت. ثبّت ffmpeg ثم أعد المحاولة.'
            )

        total = len(entries)
        with download_tasks_lock:
            task['total'] = total
            task['items'] = [
                {'title': entry.get('title') or f'Video {i+1}', 'status': 'pending'}
                for i, entry in enumerate(entries)
            ]

        playlist_dir = _create_unique_dir(DOWNLOADS_DIR / playlist_title)
        with download_tasks_lock:
            task['download_path'] = str(playlist_dir)

        completed = 0
        for i, entry in enumerate(entries):
            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            video_title = entry.get('title') or f'Video {i+1}'

            with download_tasks_lock:
                task['current_item'] = i + 1
                task['items'][i]['status'] = 'downloading'
                task['message'] = f"({i+1}/{total}) جاري تحميل: {video_title[:50]}..."
                task['status'] = 'downloading'

            output_template = str(playlist_dir / f'{i+1:03d} - %(title)s.%(ext)s')

            def make_progress_hook(index):
                def hook(d):
                    if d.get('status') != 'downloading':
                        return
                    total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    item_pct = int(downloaded_bytes / total_bytes * 100) if total_bytes > 0 else 0
                    overall_pct = int((completed + item_pct / 100) / total * 100) if total > 0 else 0
                    speed_str = _format_speed(d.get('speed'))

                    with download_tasks_lock:
                        task['progress'] = overall_pct
                        task['items'][index]['progress'] = item_pct
                        if speed_str:
                            task['message'] = (
                                f"({index + 1}/{total}) جاري تحميل: {video_title[:50]}... "
                                f"{item_pct}% | {speed_str}"
                            )

                return hook

            try:
                ydl_opts = _build_ydl_opts(task, make_progress_hook(i), output_template)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                with download_tasks_lock:
                    task['items'][i]['status'] = 'completed'
                    task['items'][i]['progress'] = 100
                completed += 1
            except Exception as e:
                with download_tasks_lock:
                    task['items'][i]['status'] = 'error'
                    task['errors'].append(f"Video {i+1}: {_friendly_error(e)}")
                completed += 1

        with download_tasks_lock:
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = f'تم تحميل الـ Playlist بنجاح! ✅ ({completed}/{total} فيديو)'
            task['finished_at'] = _now_iso()

    except Exception as e:
        friendly = _friendly_error(e)
        with download_tasks_lock:
            task['status'] = 'error'
            task['message'] = f'خطأ: {friendly}'
            task['errors'].append(friendly)
            task['finished_at'] = _now_iso()


def _run_task(task_id: str, task_type: str) -> None:
    """Run a queued task while maintaining active/queued counters."""
    global _active_downloads, _queued_downloads

    with download_tasks_lock:
        _queued_downloads = max(0, _queued_downloads - 1)
        _active_downloads += 1

    try:
        if task_type == 'playlist':
            download_playlist(task_id)
        else:
            download_single_video(task_id)
    finally:
        with download_tasks_lock:
            _active_downloads = max(0, _active_downloads - 1)
            task = download_tasks.get(task_id)
            if task is not None:
                task['finished_at'] = _now_iso()


def start_download(task_id: str):
    """Start download in background thread using ThreadPoolExecutor."""
    with download_tasks_lock:
        task = download_tasks.get(task_id)
        if task is None:
            return
        task_type = task.get('type', 'video')

    try:
        DOWNLOAD_EXECUTOR.submit(_run_task, task_id, task_type)
    except RuntimeError:
        # Executor is shut down: release the queue slot and drop the task.
        global _queued_downloads
        with download_tasks_lock:
            _queued_downloads = max(0, _queued_downloads - 1)
            download_tasks.pop(task_id, None)
        raise
