import base64
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import app


class PhotoVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        self.database.executescript("""
            CREATE TABLE photos (
                id INTEGER PRIMARY KEY, album_id INTEGER, filename TEXT,
                title TEXT, caption TEXT, visibility TEXT, created_at TEXT
            );
            CREATE TABLE photo_albums (
                id INTEGER PRIMARY KEY, name TEXT, slug TEXT,
                description TEXT, created_at TEXT
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, title TEXT, slug TEXT,
                summary TEXT, body TEXT, image_url TEXT, featured INTEGER,
                published INTEGER, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE events (starts_on TEXT, start_time TEXT);
            INSERT INTO photo_albums VALUES
                (1, 'Public album', 'public-album', '', '2026-10-01'),
                (2, 'Reserve album', 'reserve-album', '', '2026-10-01');
            INSERT INTO photos VALUES
                (1, 1, 'gallery.png', 'Gallery photo', '', 'gallery', '2026-10-01'),
                (2, 1, 'article.png', 'Article photo', '', 'article', '2026-10-01'),
                (3, 1, 'both.png', 'Shared photo', '', 'both', '2026-10-01'),
                (4, 2, 'reserve.png', 'Reserve photo', '', 'library', '2026-10-01'),
                (5, 1, 'reserve-mixed.png', 'Mixed reserve', '', 'library', '2026-10-01');
        """)
        for mock in (
            patch.object(app, "connect", return_value=self.database),
            patch.object(app, "read_settings", return_value=dict(app.DEFAULT_SETTINGS)),
        ):
            mock.start()
            self.addCleanup(mock.stop)
        self.handler = object.__new__(app.VertTigeHandler)
        self.handler.redirect = Mock()

    def change_visibility(self, visibility):
        self.handler.read_form = Mock(return_value=({"visibility": visibility, "album_id": "2"}, {}))
        self.handler.update_photo_visibility(4)

    def test_reserve_photos_and_albums_are_not_listed_publicly(self):
        for page in (
            app.home_page(),
            app.gallery_page(),
            app.gallery_page({"album": ["public-album"]}),
            app.gallery_page({"album": ["reserve-album"]}),
        ):
            self.assertNotIn("reserve.png", page)
            self.assertNotIn("reserve-mixed.png", page)
            self.assertNotIn("Reserve album", page)
            self.assertNotIn("article.png", page)
            self.assertIn("gallery.png", page)
            self.assertIn("both.png", page)
        self.assertFalse(app.site_search_results("Reserve"))
        self.assertNotIn("reserve-album", app.sitemap_xml())

    def test_all_admin_pickers_can_use_reserve_photos(self):
        admin_page = app.admin_photos_page()
        self.assertIn('value="library" selected', admin_page)
        self.assertEqual(admin_page.count('value="library"'), 6)
        for page in (admin_page, app.article_form(), app.event_form(), app.admin_home_page()):
            self.assertIn("reserve.png", page)
            self.assertIn("reserve-mixed.png", page)
        article_form = app.article_form()
        self.assertIn("article.png", article_form)
        self.assertIn("both.png", article_form)
        self.assertNotIn("gallery.png", article_form)

    def test_upload_keeps_library_status_and_file(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOZkAAAAASUVORK5CYII="
        )
        upload = app.Upload("new-reserve.png", "image/png", png)
        self.handler.read_form = Mock(return_value=(
            {"visibility": "library", "album_id": "2", "title": "Uploaded reserve"},
            {"photo": upload},
        ))
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "UPLOAD_DIR", Path(folder)):
            self.handler.upload_photo()
            row = self.database.execute("SELECT * FROM photos WHERE title = 'Uploaded reserve'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["visibility"], "library")
            self.assertEqual(row["album_id"], 2)
            self.assertEqual((Path(folder) / row["filename"]).read_bytes(), png)
            self.assertNotIn(row["filename"], app.gallery_page())
            self.assertIn(row["filename"], app.article_form())
        self.handler.redirect.assert_called_once_with("/admin/photos")

    def test_visibility_change_publishes_and_hides_without_deleting(self):
        for visibility in ("gallery", "both", "library"):
            with self.subTest(visibility=visibility):
                self.change_visibility(visibility)
                row = self.database.execute("SELECT * FROM photos WHERE id = 4").fetchone()
                self.assertEqual(row["visibility"], visibility)
                self.assertEqual(row["filename"], "reserve.png")
                visible = visibility != "library"
                self.assertEqual("reserve.png" in app.home_page(), visible)
                self.assertEqual("reserve.png" in app.gallery_page(), visible)
                self.assertEqual("reserve-album" in app.sitemap_xml(), visible)
                self.assertEqual(bool(app.site_search_results("Reserve")), visible)

    def test_published_article_keeps_its_selected_image(self):
        self.database.execute("""
            INSERT INTO articles VALUES (
                1, 'Published article', 'published', '', '',
                '/static/uploads/reserve.png', 0, 1, '2026-10-01', '2026-10-01'
            )
        """)
        self.assertIn('src="/static/uploads/reserve.png"', app.article_page("published"))
        self.assertNotIn("reserve.png", app.gallery_page())
        self.assertEqual(app.existing_photo_upload_url("/static/uploads/reserve.png"),
                         "/static/uploads/reserve.png")


if __name__ == "__main__":
    unittest.main()
