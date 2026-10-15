import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

MEDIA_TEST_ROOT = tempfile.mkdtemp(prefix="icums-media-tests-")


@override_settings(MEDIA_ROOT=MEDIA_TEST_ROOT)
class MediaServingTests(TestCase):
    """Uploads must actually be reachable, with only cover artwork public."""

    @classmethod
    def setUpTestData(cls):
        root = Path(MEDIA_TEST_ROOT)
        (root / "course_covers").mkdir(exist_ok=True)
        (root / "course_covers" / "cover.png").write_bytes(b"cover-bytes")
        (root / "module_covers").mkdir(exist_ok=True)
        (root / "module_covers" / "module.png").write_bytes(b"module-bytes")
        (root / "ucr_attachments").mkdir(exist_ok=True)
        (root / "ucr_attachments" / "upload.png").write_bytes(b"upload-bytes")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST_ROOT, ignore_errors=True)

    def test_course_cover_is_served_without_login(self):
        response = self.client.get("/media/course_covers/cover.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"cover-bytes")

    def test_module_cover_is_served_without_login(self):
        response = self.client.get("/media/module_covers/module.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"module-bytes")

    def test_other_uploads_redirect_anonymous_visitors_to_login(self):
        response = self.client.get("/media/ucr_attachments/upload.png")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_missing_upload_is_not_found(self):
        self.assertEqual(self.client.get("/media/course_covers/absent.png").status_code, 404)
