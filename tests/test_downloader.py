"""Unit tests for downloader.py.

The yt-dlp module is replaced with a fake in every test, so nothing touches the
network or the real downloads directory.
"""

import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import downloader as d


def make_task(**overrides):
    task = {
        'id': 'task-1',
        'url': 'https://www.youtube.com/watch?v=abc',
        'type': 'video',
        'quality': 'best',
        'audio_only': False,
        'status': 'pending',
        'progress': 0,
        'total': 0,
        'current_item': 0,
        'message': '',
        'items': [],
        'errors': [],
        'created_at': datetime.now().isoformat(),
        'download_path': '',
    }
    task.update(overrides)
    return task


class DownloaderTestCase(unittest.TestCase):
    def setUp(self):
        self._saved_tasks = dict(d.download_tasks)
        self._saved_active = d._active_downloads
        self._saved_queued = d._queued_downloads
        d.download_tasks.clear()
        d._active_downloads = 0
        d._queued_downloads = 0

        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self._patcher = mock.patch.object(d, 'DOWNLOADS_DIR', self.tmpdir)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()
        d.download_tasks.clear()
        d.download_tasks.update(self._saved_tasks)
        d._active_downloads = self._saved_active
        d._queued_downloads = self._saved_queued


class FilenameTests(DownloaderTestCase):
    def test_sanitize_strips_unsafe_characters(self):
        self.assertEqual(d.sanitize_filename('a/b\\c:d*e?f"g<h>i|j'), 'a_b_c_d_e_f_g_h_i_j')

    def test_sanitize_caps_length(self):
        self.assertEqual(len(d.sanitize_filename('x' * 500)), 150)

    def test_sanitize_returns_fallback_for_empty_names(self):
        for value in ('', '   ', '...', None):
            with self.subTest(value=value):
                self.assertEqual(d.sanitize_filename(value), 'download')

    def test_sanitize_prefixes_windows_reserved_names(self):
        self.assertEqual(d.sanitize_filename('CON'), '_CON')
        self.assertEqual(d.sanitize_filename('lpt1.txt'), '_lpt1.txt')


class UniqueDirTests(DownloaderTestCase):
    def test_creates_incrementing_directories(self):
        base = self.tmpdir / 'My Playlist'
        first = d._create_unique_dir(base)
        second = d._create_unique_dir(base)
        third = d._create_unique_dir(base)

        self.assertEqual(first.name, 'My Playlist')
        self.assertEqual(second.name, 'My Playlist (2)')
        self.assertEqual(third.name, 'My Playlist (3)')
        self.assertTrue(first.is_dir())
        self.assertTrue(second.is_dir())
        self.assertTrue(third.is_dir())


class TaskStoreTests(DownloaderTestCase):
    def test_get_task_returns_detached_copy(self):
        d.download_tasks['task-1'] = make_task(items=[{'title': 'x'}], errors=['boom'])

        copied = d.get_task('task-1')
        copied['items'][0]['title'] = 'changed'
        copied['errors'].append('another')

        self.assertEqual(d.download_tasks['task-1']['items'][0]['title'], 'x')
        self.assertEqual(d.download_tasks['task-1']['errors'], ['boom'])

    def test_get_task_unknown_returns_empty_dict(self):
        self.assertEqual(d.get_task('missing'), {})

    def test_cleanup_removes_only_old_terminal_tasks(self):
        old = (datetime.now() - timedelta(hours=2)).isoformat()
        now = datetime.now().isoformat()
        d.download_tasks['old-done'] = make_task(status='completed', finished_at=old)
        d.download_tasks['old-error'] = make_task(status='error', created_at=old)
        d.download_tasks['old-pending'] = make_task(status='pending', created_at=old)
        d.download_tasks['new-done'] = make_task(status='completed', finished_at=now)

        d._cleanup_old_tasks()

        self.assertNotIn('old-done', d.download_tasks)
        self.assertNotIn('old-error', d.download_tasks)
        self.assertIn('old-pending', d.download_tasks)
        self.assertIn('new-done', d.download_tasks)

    def test_capacity_limit_raises(self):
        with mock.patch.object(d, '_active_downloads', d.MAX_ACTIVE_DOWNLOADS), \
                mock.patch.object(d, '_queued_downloads', d.MAX_QUEUED_TASKS):
            with self.assertRaises(d.TaskLimitExceeded):
                d.create_task('https://youtu.be/abc', 'video', 'best', False)

    def test_create_task_reserves_a_queue_slot(self):
        task_id = d.create_task('https://youtu.be/abc', 'video', 'best', False)
        self.assertIn(task_id, d.download_tasks)
        self.assertEqual(d.get_stats(), {'active': 0, 'queued': 1})


class YdlOptionsTests(DownloaderTestCase):
    def hook(self, _event):
        pass

    def test_always_disables_playlist_expansion(self):
        with mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            opts = d._build_ydl_opts(make_task(), self.hook, '/tmp/%(title)s.%(ext)s')
        self.assertTrue(opts['noplaylist'])
        self.assertEqual(opts['retries'], 3)

    def test_falls_back_to_progressive_without_ffmpeg(self):
        with mock.patch.object(d, 'find_ffmpeg', return_value=None):
            opts = d._build_ydl_opts(make_task(), self.hook, '/tmp/out.%(ext)s')

        self.assertEqual(opts['format'], 'best[ext=mp4]/best')
        self.assertNotIn('merge_output_format', opts)
        self.assertNotIn('ffmpeg_location', opts)

    def test_audio_without_ffmpeg_raises(self):
        with mock.patch.object(d, 'find_ffmpeg', return_value=None):
            with self.assertRaises(RuntimeError):
                d._build_ydl_opts(
                    make_task(audio_only=True), self.hook, '/tmp/out.%(ext)s'
                )

    def test_merge_and_ffmpeg_location_with_ffmpeg(self):
        with mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            opts = d._build_ydl_opts(make_task(), self.hook, '/tmp/out.%(ext)s')

        self.assertEqual(opts['merge_output_format'], 'mp4')
        self.assertEqual(opts['ffmpeg_location'], '/usr/bin')

    def test_invalid_quality_raises(self):
        with mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            with self.assertRaises(ValueError):
                d._build_ydl_opts(
                    make_task(quality='8k'), self.hook, '/tmp/out.%(ext)s'
                )

    def test_cookies_file_is_passed_when_present(self):
        cookies = self.tmpdir / 'cookies.txt'
        cookies.write_text('# Netscape HTTP Cookie File\n', encoding='utf-8')

        with mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'), \
                mock.patch.dict(os.environ, {'COOKIES_FILE': str(cookies)}):
            opts = d._build_ydl_opts(make_task(), self.hook, '/tmp/out.%(ext)s')

        self.assertEqual(opts['cookiefile'], str(cookies))


class FakeYoutubeDL:
    """Minimal yt-dlp context-manager double."""

    def __init__(self, opts, fail=False):
        self.opts = opts
        self.fail = fail

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def download(self, urls):
        if self.fail:
            raise RuntimeError('boom')
        hook = self.opts['progress_hooks'][0]
        hook({
            'status': 'downloading',
            'total_bytes': 100,
            'downloaded_bytes': 40,
            'speed': 2048,
            'eta': 3,
        })
        hook({'status': 'finished'})

    def extract_info(self, url, download=False):
        return {
            '_type': 'playlist',
            'title': 'My Playlist',
            'entries': [{'title': 'First', 'id': 'abc'}],
        }


class FriendlyErrorTests(DownloaderTestCase):
    def test_explains_ffmpeg_requirement_for_modern_videos(self):
        exc = Exception(
            'ERROR: [youtube] abc: Requested format is not available. Use --list-formats'
        )
        with mock.patch.object(d, 'find_ffmpeg', return_value=None):
            message = d._friendly_error(exc)

        self.assertIn('ffmpeg', message)
        self.assertIn('install_ffmpeg.py', message)
        self.assertNotIn('Use --list-formats', message)

    def test_keeps_original_error_when_ffmpeg_is_available(self):
        exc = Exception('ERROR: Requested format is not available')
        with mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            self.assertEqual(d._friendly_error(exc), str(exc))

    def test_keeps_unrelated_errors(self):
        exc = Exception('ERROR: This video is unavailable')
        with mock.patch.object(d, 'find_ffmpeg', return_value=None):
            self.assertEqual(d._friendly_error(exc), str(exc))


class DownloadExecutionTests(DownloaderTestCase):
    def fake_yt_dlp(self, fail=False):
        module = types.ModuleType('yt_dlp')
        module.YoutubeDL = lambda opts: FakeYoutubeDL(opts, fail=fail)
        return module

    def test_single_video_completes_and_stamps_finished_at(self):
        d.download_tasks['task-1'] = make_task()

        with mock.patch.dict(sys.modules, {'yt_dlp': self.fake_yt_dlp()}), \
                mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            d.download_single_video('task-1')

        task = d.download_tasks['task-1']
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['progress'], 100)
        self.assertIn('finished_at', task)

    def test_single_video_failure_marks_error(self):
        d.download_tasks['task-1'] = make_task()

        with mock.patch.dict(sys.modules, {'yt_dlp': self.fake_yt_dlp(fail=True)}), \
                mock.patch.object(d, 'find_ffmpeg', return_value='/usr/bin/ffmpeg'):
            d.download_single_video('task-1')

        task = d.download_tasks['task-1']
        self.assertEqual(task['status'], 'error')
        self.assertTrue(task['errors'])
        self.assertIn('finished_at', task)

    def test_playlist_audio_without_ffmpeg_fails_fast(self):
        d.download_tasks['task-1'] = make_task(
            type='playlist', audio_only=True,
            url='https://www.youtube.com/playlist?list=abc',
        )

        with mock.patch.dict(sys.modules, {'yt_dlp': self.fake_yt_dlp()}), \
                mock.patch.object(d, 'find_ffmpeg', return_value=None):
            d.download_playlist('task-1')

        task = d.download_tasks['task-1']
        self.assertEqual(task['status'], 'error')
        self.assertIn('ffmpeg', task['message'])

    def test_run_task_releases_counters(self):
        d.download_tasks['task-1'] = make_task()
        d._queued_downloads = 1

        with mock.patch.object(d, 'download_single_video') as run:
            d._run_task('task-1', 'video')

        run.assert_called_once_with('task-1')
        self.assertEqual(d.get_stats(), {'active': 0, 'queued': 0})
        self.assertIn('finished_at', d.download_tasks['task-1'])


if __name__ == '__main__':
    unittest.main()
