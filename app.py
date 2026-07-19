"""
YouTube Downloader - Flask Backend Server
"""

from flask import Flask, jsonify, request, send_from_directory, send_file, Response
from flask_cors import CORS
import os
import json
import time
import platform
import subprocess
from pathlib import Path
from downloader import (
    get_video_info, create_task, get_task,
    start_download, DOWNLOADS_DIR
)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)


@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'version': '2.0.0'})


@app.route('/api/info', methods=['POST'])
def api_info():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'الرجاء إدخال بيانات صحيحة'}), 400

    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط صحيح'}), 400

    if not any(domain in url for domain in ['youtube.com', 'youtu.be']):
        return jsonify({'error': 'الرجاء إدخال رابط يوتيوب صحيح'}), 400

    try:
        info = get_video_info(url)
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'الرجاء إدخال بيانات صحيحة'}), 400

    url = data.get('url', '').strip()
    download_type = data.get('type', 'video')
    quality = data.get('quality', 'best')
    audio_only = data.get('audio_only', False)

    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط صحيح'}), 400

    if download_type not in ('video', 'playlist'):
        return jsonify({'error': 'نوع التحميل غير صحيح'}), 400

    task_id = create_task(url, download_type, quality, audio_only)
    start_download(task_id)

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
    def generate():
        timeout = 0
        while timeout < 3600:
            task = get_task(task_id)
            if not task:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break

            payload = {
                'status': task.get('status'),
                'progress': task.get('progress', 0),
                'total': task.get('total', 0),
                'current_item': task.get('current_item', 0),
                'message': task.get('message', ''),
                'items': task.get('items', []),
                'errors': task.get('errors', []),
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if task.get('status') in ('completed', 'error'):
                break

            time.sleep(0.5)
            timeout += 0.5

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
        except ValueError:
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
                count = len([f for f in item.iterdir() if not f.name.startswith('.')])
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

    if folder:
        target_dir = DOWNLOADS_DIR / folder
    else:
        target_dir = DOWNLOADS_DIR

    file_path = target_dir / filename

    # Prevent path traversal
    try:
        file_path.resolve().relative_to(DOWNLOADS_DIR.resolve())
    except ValueError:
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
        return jsonify({
            'success': False,
            'opened': False,
            'path': str(DOWNLOADS_DIR),
            'error': str(e)
        })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  YouTube Downloader Server v2.0")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
