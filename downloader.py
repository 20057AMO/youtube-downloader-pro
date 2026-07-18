"""
YouTube Downloader - Core Download Logic
Uses yt-dlp for reliable downloading.
"""

import os
import re
import sys
import uuid
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=3)
download_tasks = {}
download_tasks_lock = threading.Lock()
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

TASK_MAX_AGE = 3600


def _cleanup_old_tasks():
    now = datetime.now().timestamp()
    expired = [
        tid for tid, t in download_tasks.items()
        if now - datetime.fromisoformat(t["created_at"]).timestamp() > TASK_MAX_AGE
        and t.get("status") in ("completed", "error")
    ]
    for tid in expired:
        download_tasks.pop(tid, None)


def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    return filename[:200] if len(filename) > 200 else filename


def get_task(task_id: str) -> dict:
    with download_tasks_lock:
        task = download_tasks.get(task_id, {})
    return task


def create_task(url: str, download_type: str, quality: str, audio_only: bool) -> str:
    _cleanup_old_tasks()
    task_id = str(uuid.uuid4())
    with download_tasks_lock:
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
            "created_at": datetime.now().isoformat(),
            "download_path": str(DOWNLOADS_DIR)
        }
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
            info = ydl.extract_info(url, download=False)

            if info.get('_type') == 'playlist':
                entries = info.get('entries', [])
                return {
                    "type": "playlist",
                    "title": info.get('title', 'Unknown Playlist'),
                    "uploader": info.get('uploader', 'Unknown'),
                    "count": len(entries),
                    "thumbnail": info.get('thumbnail') or (
                        entries[0].get('thumbnail') if entries else None
                    ),
                    "items": [
                        {
                            "title": e.get('title', f'Video {i+1}'),
                            "url": e.get('url') or f"https://www.youtube.com/watch?v={e.get('id', '')}",
                            "duration": e.get('duration'),
                            "thumbnail": e.get('thumbnail'),
                        }
                        for i, e in enumerate(entries) if e
                    ]
                }
            else:
                formats = info.get('formats', [])
                available_qualities = set()
                for f in formats:
                    h = f.get('height')
                    if h and f.get('vcodec') != 'none':
                        available_qualities.add(h)

                return {
                    "type": "video",
                    "title": info.get('title', 'Unknown Video'),
                    "uploader": info.get('uploader', 'Unknown'),
                    "duration": info.get('duration'),
                    "thumbnail": info.get('thumbnail'),
                    "description": info.get('description', '')[:300],
                    "view_count": info.get('view_count', 0),
                    "available_qualities": sorted(list(available_qualities), reverse=True),
                    "url": url
                }
    except Exception as e:
        raise Exception(f"فشل في جلب المعلومات: {str(e)}")


def _build_ydl_opts(task: dict, progress_hook, output_template: str) -> dict:
    quality = task.get('quality', 'best')
    audio_only = task.get('audio_only', False)

    if audio_only:
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
        q = quality_map.get(quality, 'best')
        if q == 'best':
            format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        else:
            format_str = (
                f'bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]'
                f'/bestvideo[height<={q}]+bestaudio/best'
            )
        postprocessors = []

    ffmpeg_path = os.path.join(os.path.dirname(sys.executable), 'ffmpeg')
    if not os.path.exists(ffmpeg_path):
        ffmpeg_path = shutil.which('ffmpeg') or 'ffmpeg'

    opts = {
        'format': format_str,
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4' if not audio_only else None,
        'ffmpeg_location': os.path.dirname(ffmpeg_path) if os.path.dirname(ffmpeg_path) else None,
    }
    if audio_only:
        opts['postprocessors'] = postprocessors
        opts.pop('merge_output_format', None)

    return opts


def download_single_video(task_id: str, url: str = None):
    """Download a single video."""
    import yt_dlp
    with download_tasks_lock:
        task = download_tasks[task_id]
    target_url = url or task['url']

    try:
        output_template = str(DOWNLOADS_DIR / '%(title)s.%(ext)s')

        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)

                pct = int(downloaded / total * 100) if total > 0 else 0

                speed_str = ""
                if speed:
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024*1024):.1f} MB/s"
                    else:
                        speed_str = f"{speed / 1024:.0f} KB/s"

                eta_str = f" | ETA: {eta}s" if eta else ""

                with download_tasks_lock:
                    task['progress'] = pct
                    task['message'] = f"جاري التحميل... {pct}% | {speed_str}{eta_str}"
                    task['status'] = 'downloading'

            elif d['status'] == 'finished':
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

    except Exception as e:
        with download_tasks_lock:
            task['status'] = 'error'
            task['message'] = f'خطأ: {str(e)}'
            task['errors'].append(str(e))


def download_playlist(task_id: str):
    """Download entire playlist."""
    import yt_dlp
    with download_tasks_lock:
        task = download_tasks[task_id]
    url = task['url']

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
            info = ydl.extract_info(url, download=False)

        if info.get('_type') == 'playlist':
            entries = [e for e in info.get('entries', []) if e]
            playlist_title = sanitize_filename(info.get('title', 'playlist'))
        else:
            entries = [info]
            playlist_title = sanitize_filename(info.get('title', 'video'))

        total = len(entries)
        with download_tasks_lock:
            task['total'] = total
            task['items'] = [
                {'title': e.get('title', f'Video {i+1}'), 'status': 'pending'}
                for i, e in enumerate(entries)
            ]

        playlist_dir = DOWNLOADS_DIR / playlist_title
        playlist_dir.mkdir(exist_ok=True)

        completed = 0
        for i, entry in enumerate(entries):
            if not entry:
                continue

            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            video_title = entry.get('title', f'Video {i+1}')

            with download_tasks_lock:
                task['current_item'] = i + 1
                task['items'][i]['status'] = 'downloading'
                task['message'] = f"({i+1}/{total}) جاري تحميل: {video_title[:50]}..."
                task['status'] = 'downloading'

            output_template = str(playlist_dir / f'{i+1:03d} - %(title)s.%(ext)s')

            def make_progress_hook(idx):
                def hook(d):
                    if d['status'] == 'downloading':
                        total_b = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        downloaded_b = d.get('downloaded_bytes', 0)
                        speed = d.get('speed', 0)

                        item_pct = int(downloaded_b / total_b * 100) if total_b > 0 else 0
                        overall_pct = int((completed + item_pct / 100) / total * 100)

                        speed_str = ""
                        if speed:
                            if speed > 1024 * 1024:
                                speed_str = f" | {speed / (1024*1024):.1f} MB/s"
                            else:
                                speed_str = f" | {speed / 1024:.0f} KB/s"

                        with download_tasks_lock:
                            task['progress'] = overall_pct
                            task['items'][idx]['progress'] = item_pct

                return hook

            try:
                ydl_opts = _build_ydl_opts(task, make_progress_hook(i), output_template)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                with download_tasks_lock:
                    task['items'][i]['status'] = 'completed'
                completed += 1
            except Exception as e:
                with download_tasks_lock:
                    task['items'][i]['status'] = 'error'
                    task['errors'].append(f"Video {i+1}: {str(e)}")
                completed += 1

        with download_tasks_lock:
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = f'تم تحميل الـ Playlist بنجاح! ✅ ({completed}/{total} فيديو)'

    except Exception as e:
        with download_tasks_lock:
            task['status'] = 'error'
            task['message'] = f'خطأ: {str(e)}'
            task['errors'].append(str(e))


def start_download(task_id: str):
    """Start download in background thread using ThreadPoolExecutor."""
    task = download_tasks.get(task_id)
    if not task:
        return

    if task['type'] == 'playlist':
        DOWNLOAD_EXECUTOR.submit(download_playlist, task_id)
    else:
        DOWNLOAD_EXECUTOR.submit(download_single_video, task_id)
