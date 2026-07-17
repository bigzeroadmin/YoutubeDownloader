import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DESKTOP_MODE", "1")

from app.models import TaskInfo  # noqa: E402
from app.worker import _run_ytdlp  # noqa: E402


class _FakeYoutubeDL:
    last_options = None

    def __init__(self, options):
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def download(self, urls):
        return None


class WorkerFormatSelectionTests(unittest.TestCase):
    def run_task(self, task):
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.worker.yt_dlp.YoutubeDL", _FakeYoutubeDL):
                _run_ytdlp(task, Path(directory))
        return _FakeYoutubeDL.last_options

    def test_progressive_video_keeps_its_existing_audio(self):
        options = self.run_task(
            TaskInfo(format_id="tiktok-h264", has_audio=True)
        )

        self.assertEqual(options["format"], "tiktok-h264")
        self.assertNotIn("merge_output_format", options)

    def test_video_only_format_is_merged_with_best_audio(self):
        options = self.run_task(TaskInfo(format_id="youtube-video-only"))

        self.assertEqual(
            options["format"],
            "youtube-video-only+bestaudio/youtube-video-only/best",
        )
        self.assertEqual(options["merge_output_format"], "mp4")


if __name__ == "__main__":
    unittest.main()
