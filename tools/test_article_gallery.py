import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app


class ArticleGalleryTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        self.database.executescript("""
            CREATE TABLE photos (
                id INTEGER PRIMARY KEY, album_id INTEGER, filename TEXT,
                title TEXT, caption TEXT, visibility TEXT, created_at TEXT
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY, title TEXT, slug TEXT UNIQUE,
                summary TEXT, body TEXT, image_url TEXT, featured INTEGER,
                published INTEGER, gallery_urls TEXT NOT NULL DEFAULT '[]',
                created_at TEXT, updated_at TEXT
            );
            CREATE TABLE events (image_url TEXT);
            INSERT INTO photos VALUES (1, NULL, 'bank.png', 'Bank', '', 'article', '2026-10-01');
            INSERT INTO articles (id, title, slug, summary, body, image_url, featured, published, created_at, updated_at)
            VALUES (1, 'Récolte', 'recolte', '', 'Texte', '/static/hero-garden.png', 0, 1, '2026-10-01', '2026-10-01');
        """)
        self.upload_dir = Path(tempfile.mkdtemp())
        for mock in (
            patch.object(app, "connect", return_value=self.database),
            patch.object(app, "read_settings", return_value=dict(app.DEFAULT_SETTINGS)),
            patch.object(app, "UPLOAD_DIR", self.upload_dir),
        ):
            mock.start()
            self.addCleanup(mock.stop)
        self.handler = object.__new__(app.VertTigeHandler)
        self.handler.redirect = Mock()

    def test_multiple_files_with_same_field_name_are_kept(self):
        boundary = "XyZ"
        parts = "".join(
            f'--{boundary}\r\nContent-Disposition: form-data; name="article_gallery"; filename="p{i}.png"\r\n'
            f"Content-Type: image/png\r\n\r\ndata{i}\r\n"
            for i in range(3)
        )
        body = (parts + f"--{boundary}--\r\n").encode()
        _, files = app.parse_multipart(f"multipart/form-data; boundary={boundary}", body)
        uploads = app.uploads_named(files, "article_gallery")
        self.assertEqual([upload.filename for upload in uploads], ["p0.png", "p1.png", "p2.png"])

    def test_article_gallery_is_saved_rendered_and_cleaned_on_photo_delete(self):
        form = {"title": "Récolte", "published": "1", "gallery_photo_1": "/static/uploads/bank.png"}
        files = {
            "article_gallery": app.Upload("a.png", "image/png", b"a"),
            "article_gallery#2": app.Upload("b.png", "image/png", b"b"),
        }
        self.handler.read_form = Mock(return_value=(form, files))
        self.handler.save_article(1)

        gallery = json.loads(self.database.execute("SELECT gallery_urls FROM articles").fetchone()[0])
        self.assertEqual(len(gallery), 3)
        self.assertEqual(gallery[0], "/static/uploads/bank.png")
        page = app.article_page("recolte")
        for url in gallery:
            self.assertIn(f'src="{url}"', page)
        self.assertIn("gallery_photo_1", app.article_form(self.database.execute("SELECT * FROM articles").fetchone()))

        self.handler.delete_photo(1)
        gallery = json.loads(self.database.execute("SELECT gallery_urls FROM articles").fetchone()[0])
        self.assertNotIn("/static/uploads/bank.png", gallery)
        self.assertEqual(len(gallery), 2)


if __name__ == "__main__":
    unittest.main()

