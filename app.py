"""
YouTube Downloader - Flask Backend Server
"""

from flask import Flask, jsonify, request, send_from_directory, Response
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
    files = []
    if DOWNLOADS_DIR.exists():
        for item in DOWNLOADS_DIR.iterdir():
            if item.name.startswith('.'):
                continue
            if item.is_file():
                files.append({
                    'name': item.name,
                    'size': item.stat().st_size,
                    'type': 'file'
                })
            elif item.is_dir():
                count = len(list(item.iterdir()))
                files.append({
                    'name': item.name,
                    'count': count,
                    'type': 'folder'
                })

    return jsonify({'files': sorted(files, key=lambda x: x['name'])})


@app.route('/api/open-folder', methods=['POST'])
def api_open_folder():
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(f'explorer "{DOWNLOADS_DIR}"')
        elif system == "Darwin":
            subprocess.Popen(['open', str(DOWNLOADS_DIR)])
        else:
            subprocess.Popen(['xdg-open', str(DOWNLOADS_DIR)])

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 50)
    print("  YouTube Downloader Server v2.0")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
