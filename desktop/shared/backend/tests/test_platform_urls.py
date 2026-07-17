import unittest

from app.services.ytdlp_service import validate_url


class ValidatePlatformUrlTests(unittest.TestCase):
    def test_accepts_tiktok_video_and_short_links(self):
        urls = [
            "https://www.tiktok.com/@creator/video/1234567890",
            "https://m.tiktok.com/v/1234567890.html",
            "https://vm.tiktok.com/abc123/",
            "https://vt.tiktok.com/xyz789/",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_keeps_accepting_youtube_links(self):
        urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://music.youtube.com/watch?v=abc123",
            "https://youtu.be/abc123",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_accepts_douyin_video_and_short_links(self):
        urls = [
            "https://www.douyin.com/video/1234567890",
            "https://douyin.com/video/1234567890",
            "https://v.douyin.com/abc123/",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_rejects_lookalike_and_unsupported_hosts(self):
        urls = [
            "https://tiktok.com.evil.example/video/123",
            "https://youtube.com.evil.example/watch?v=abc123",
            "https://douyin.com.evil.example/video/123",
            "https://example.com/video/123",
            "file:///tmp/video.mp4",
        ]

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_url(url)


if __name__ == "__main__":
    unittest.main()
