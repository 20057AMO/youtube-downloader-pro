"""HTTP-level regression tests for the Flask API.

All external calls are mocked: these tests never touch the network, yt-dlp or
the real downloads directory.
"""

import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app as app_module
from downloader import TaskLimitExceeded


VALID_VIDEO_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'

BAD_URLS = [
    'https://example.com',
    'https://example.com/?youtube.com',
    'https://youtube.com.evil.example/watch?v=1',
    'https://www.youtube.com@evil.example/watch?v=1',
    'javascript:alert(1)',
    'file:///etc/passwd',
    'ftp://youtube.com/file',
    '',
    '   ',
    None,
    123,
]

ALLOWED_URLS = [
    'https://youtube.com/watch?v=abc',
    'https://www.youtube.com/watch?v=abc',
    'https://m.youtube.com/watch?v=abc',
    'https://music.youtube.com/watch?v=abc',
    'https://gaming.youtube.com/watch?v=abc',
    'https://youtu.be/abc',
    'https://www.youtu.be/abc',
    'https://youtube-nocookie.com/embed/abc',
    'https://www.youtube-nocookie.com/embed/abc',
]


class ApiTestCase(unittest.TestCase):
    """Base fixture: fresh client, clean env and a temp downloads directory."""

    def setUp(self):
        app_module.app.config.update(TESTING=True)
        self.client = app_module.app.test_client()
        self._saved_env = dict(os.environ)
        for name in ('APP_USERNAME', 'APP_PASSWORD', 'TRUST_PROXY', 'RATE_LIMIT_PER_MINUTE'):
            os.environ.pop(name, None)
        app_module._rate_limit_buckets.clear()

        self._tmp = tempfile.TemporaryDirectory()
        self.downloads_dir = Path(self._tmp.name)
        self._patches = [
            mock.patch.object(app_module, 'DOWNLOADS_DIR', self.downloads_dir),
        ]
        for patcher in self._patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self._patches):
            patcher.stop()
        self._tmp.cleanup()
        os.environ.clear()
        os.environ.update(self._saved_env)
        app_module._rate_limit_buckets.clear()

    # -- helpers ---------------------------------------------------------
    def post_info(self, url, **kwargs):
        return self.client.post('/api/info', json={'url': url}, **kwargs)

    def post_download(self, **payload):
        body = {
            'url': VALID_VIDEO_URL,
            'type': 'video',
            'quality': 'best',
            'audio_only': False,
        }
        body.update(payload)
        return self.client.post('/api/download', json=body)


class HealthTests(ApiTestCase):
    def test_health_shape(self):
        with mock.patch.object(app_module, 'ffmpeg_available', return_value=True):
            response = self.client.get('/api/health')

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for key in ('status', 'version', 'ytdlp', 'ffmpeg', 'auth', 'active', 'queued'):
            self.assertIn(key, data)
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['ffmpeg'])

    def test_api_responses_are_not_cached(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')


class InfoTests(ApiTestCase):
    def test_rejects_non_youtube_urls_without_calling_ytdlp(self):
        with mock.patch.object(app_module, 'get_video_info') as fetch_info:
            for url in BAD_URLS:
                with self.subTest(url=url):
                    response = self.post_info(url)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('error', response.get_json())
            fetch_info.assert_not_called()

    def test_accepts_allowlisted_hosts(self):
        info = {'type': 'video', 'title': 'Example'}
        with mock.patch.object(app_module, 'get_video_info', return_value=info):
            for url in ALLOWED_URLS:
                with self.subTest(url=url):
                    response = self.post_info(url)
                    self.assertEqual(response.status_code, 200)
                    data = response.get_json()
                    self.assertTrue(data['success'])
                    self.assertEqual(data['info'], info)

    def test_missing_and_non_string_url_returns_400(self):
        for payload in ({}, {'url': None}, {'url': 42}, {'url': ['x']}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/info', json=payload)
                self.assertEqual(response.status_code, 400)

    def test_malformed_json_returns_json_400(self):
        response = self.client.post(
            '/api/info', data='{"url": ', content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.get_json())

    def test_oversized_body_returns_413(self):
        response = self.client.post(
            '/api/download',
            data='x' * (17 * 1024),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn('error', response.get_json())


class DownloadValidationTests(ApiTestCase):
    def test_rejects_invalid_type(self):
        for value in ('audio', '', None, ['video']):
            with self.subTest(type=value):
                response = self.post_download(type=value)
                self.assertEqual(response.status_code, 400)

    def test_rejects_invalid_quality(self):
        for value in ('4k', '', None, 1080):
            with self.subTest(quality=value):
                response = self.post_download(quality=value)
                self.assertEqual(response.status_code, 400)

    def test_rejects_non_youtube_url(self):
        with mock.patch.object(app_module, 'create_task') as create:
            response = self.post_download(url='http://127.0.0.1:5000/api/health')
        self.assertEqual(response.status_code, 400)
        create.assert_not_called()

    def test_enqueues_valid_download(self):
        with mock.patch.object(app_module, 'create_task', return_value='task-1') as create, \
                mock.patch.object(app_module, 'start_download') as start:
            response = self.post_download()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'success': True, 'task_id': 'task-1'})
        create.assert_called_once_with(VALID_VIDEO_URL, 'video', 'best', False)
        start.assert_called_once_with('task-1')

    def test_audio_only_requires_real_boolean(self):
        with mock.patch.object(app_module, 'create_task', return_value='task-1') as create, \
                mock.patch.object(app_module, 'start_download'):
            response = self.post_download(audio_only='true')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(create.call_args.args[3])

    def test_task_limit_maps_to_429(self):
        with mock.patch.object(app_module, 'create_task', side_effect=TaskLimitExceeded()), \
                mock.patch.object(app_module, 'start_download'):
            response = self.post_download()

        self.assertEqual(response.status_code, 429)
        self.assertIn('error', response.get_json())


class RateLimitTests(ApiTestCase):
    def test_limit_returns_429_with_retry_after(self):
        os.environ['RATE_LIMIT_PER_MINUTE'] = '2'
        with mock.patch.object(app_module, 'get_video_info', return_value={}):
            self.assertEqual(self.post_info(VALID_VIDEO_URL).status_code, 200)
            self.assertEqual(self.post_info(VALID_VIDEO_URL).status_code, 200)
            blocked = self.post_info(VALID_VIDEO_URL)

        self.assertEqual(blocked.status_code, 429)
        self.assertIsNotNone(blocked.headers.get('Retry-After'))

    def test_forwarded_for_is_ignored_by_default(self):
        os.environ['RATE_LIMIT_PER_MINUTE'] = '1'
        with mock.patch.object(app_module, 'get_video_info', return_value={}):
            first = self.post_info(VALID_VIDEO_URL, headers={'X-Forwarded-For': '1.1.1.1'})
            second = self.post_info(VALID_VIDEO_URL, headers={'X-Forwarded-For': '2.2.2.2'})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_forwarded_for_is_honoured_when_trusted(self):
        os.environ['RATE_LIMIT_PER_MINUTE'] = '1'
        os.environ['TRUST_PROXY'] = '1'
        with mock.patch.object(app_module, 'get_video_info', return_value={}):
            first = self.post_info(VALID_VIDEO_URL, headers={'X-Forwarded-For': '1.1.1.1'})
            second = self.post_info(VALID_VIDEO_URL, headers={'X-Forwarded-For': '2.2.2.2'})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)


class AuthTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.username = 'admin'
        self.password = 's3cret'
        os.environ['APP_USERNAME'] = self.username
        os.environ['APP_PASSWORD'] = self.password

    @staticmethod
    def basic_header(username, password):
        token = base64.b64encode(f'{username}:{password}'.encode()).decode()
        return {'Authorization': f'Basic {token}'}

    def test_protected_route_requires_credentials(self):
        response = self.post_info(VALID_VIDEO_URL)
        self.assertEqual(response.status_code, 401)
        self.assertIn('Basic', response.headers.get('WWW-Authenticate', ''))

    def test_wrong_credentials_rejected(self):
        response = self.post_info(
            VALID_VIDEO_URL, headers=self.basic_header(self.username, 'wrong')
        )
        self.assertEqual(response.status_code, 401)

    def test_valid_credentials_reach_handler(self):
        with mock.patch.object(app_module, 'get_video_info', return_value={}):
            response = self.post_info(
                VALID_VIDEO_URL, headers=self.basic_header(self.username, self.password)
            )
        self.assertEqual(response.status_code, 200)

    def test_health_is_exempt(self):
        self.assertEqual(self.client.get('/api/health').status_code, 200)


class ProgressTests(ApiTestCase):
    def test_unknown_task_returns_404(self):
        self.assertEqual(self.client.get('/api/progress/missing').status_code, 404)

    def test_progress_includes_type(self):
        task = {
            'id': 't1', 'status': 'downloading', 'type': 'playlist',
            'progress': 10, 'total': 5, 'current_item': 1,
            'message': '...', 'items': [], 'errors': [],
        }
        with mock.patch.object(app_module, 'get_task', return_value=task):
            response = self.client.get('/api/progress/t1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['type'], 'playlist')


class StreamTests(ApiTestCase):
    def test_unknown_task_returns_404(self):
        self.assertEqual(self.client.get('/api/stream/missing').status_code, 404)

    def test_stream_starts_with_retry_and_includes_type(self):
        task = {
            'id': 't1', 'status': 'completed', 'type': 'playlist',
            'progress': 100, 'total': 2, 'current_item': 2,
            'message': 'done', 'items': [], 'errors': [],
        }
        with mock.patch.object(app_module, 'get_task', return_value=task):
            response = self.client.get('/api/stream/t1')
            body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.startswith('retry: 2000'))
        self.assertIn('"type": "playlist"', body)


class DownloadFileTests(ApiTestCase):
    def test_downloads_rejects_traversal(self):
        response = self.client.get('/api/downloads?folder=../../etc')
        self.assertEqual(response.status_code, 400)

    def test_download_file_rejects_traversal(self):
        for name in ('../../requirements.txt', '..%2F..%2Fetc%2Fpasswd', '.', '..', 'a/b'):
            with self.subTest(name=name):
                response = self.client.get(f'/api/download-file?name={name}')
                self.assertEqual(response.status_code, 400)

    def test_download_file_serves_existing_file(self):
        target = self.downloads_dir / 'clip.mp4'
        target.write_bytes(b'video-bytes')

        response = self.client.get('/api/download-file?name=clip.mp4')
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b'video-bytes')
            self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        finally:
            response.close()

    def test_download_file_missing_returns_404(self):
        response = self.client.get('/api/download-file?name=missing.mp4')
        self.assertEqual(response.status_code, 404)

    def test_downloads_lists_files_and_folders(self):
        (self.downloads_dir / 'one.mp4').write_bytes(b'x')
        folder = self.downloads_dir / 'Playlist'
        folder.mkdir()
        (folder / 'a.mp4').write_bytes(b'x')
        (folder / 'b.mp4').write_bytes(b'x')

        response = self.client.get('/api/downloads')
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        by_name = {item['name']: item for item in data['files']}
        self.assertEqual(by_name['one.mp4']['type'], 'file')
        self.assertEqual(by_name['Playlist']['type'], 'folder')
        self.assertEqual(by_name['Playlist']['count'], 2)


class CorsTests(ApiTestCase):
    def test_no_cors_headers_by_default(self):
        if app_module._cors_origins:
            self.skipTest('CORS_ORIGINS was set when the module was imported')
        response = self.client.get('/api/health')
        self.assertNotIn('Access-Control-Allow-Origin', response.headers)


if __name__ == '__main__':
    unittest.main()
