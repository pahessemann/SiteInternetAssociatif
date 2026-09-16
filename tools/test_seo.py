import http.client
import sqlite3
import threading
import unittest
from unittest.mock import patch

import app


class PublicArticleSeoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database = sqlite3.connect(":memory:", check_same_thread=False)
        database.row_factory = sqlite3.Row
        cls.addClassCleanup(database.close)
        with database as conn:
            conn.execute("""
                CREATE TABLE articles (
                    title TEXT, slug TEXT, summary TEXT, body TEXT,
                    image_url TEXT, published INTEGER,
                    created_at TEXT, updated_at TEXT
                )
            """)
            conn.executemany(
                "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("Published garden news", "published", "Summary", "Body", "", 1,
                     "2026-09-16T10:00:00", "2026-09-16T10:00:00"),
                    ("Private draft", "draft", "Secret summary", "Secret body", "", 0,
                     "2026-09-16T10:00:00", "2026-09-16T10:00:00"),
                ],
            )
        for mock in (
            patch.object(app, "connect", return_value=database),
            patch.object(app, "PUBLIC_URL", "https://jardin-vert-tige.fr"),
            patch.object(app, "read_settings", return_value=dict(app.DEFAULT_SETTINGS)),
            patch.object(app, "write_log"),
        ):
            mock.start()
            cls.addClassCleanup(mock.stop)
        cls.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.VertTigeHandler)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.thread.join)
        cls.addClassCleanup(cls.server.shutdown)

    def get(self, path):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def test_published_article_remains_indexable(self):
        status, body = self.get("/articles/published")
        self.assertEqual(status, 200)
        self.assertIn("<h1>Published garden news</h1>", body)
        self.assertIn('rel="canonical" href="https://jardin-vert-tige.fr/articles/published"', body)
        self.assertNotIn('content="noindex, nofollow"', body)

    def test_missing_and_unpublished_articles_are_http_404(self):
        for path in ("/articles/missing", "/articles/draft", "/missing-page"):
            with self.subTest(path=path):
                status, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertIn('content="noindex, nofollow"', body)
                self.assertNotIn("Private draft", body)
                self.assertNotIn("Secret body", body)


class OrganizationSeoTests(unittest.TestCase):
    def test_placeholder_email_is_not_advertised_to_search_engines(self):
        for email in ("contact@vert-tige.local", "CONTACT@VERT-TIGE.LOCAL", "", "invalid"):
            with self.subTest(email=email):
                settings = dict(app.DEFAULT_SETTINGS, contact_email=email)
                self.assertNotIn("email", app.organization_schema(settings))

    def test_configured_email_is_preserved(self):
        settings = dict(app.DEFAULT_SETTINGS, contact_email="contact@example.org")
        self.assertEqual(app.organization_schema(settings)["email"], "contact@example.org")


if __name__ == "__main__":
    unittest.main()
