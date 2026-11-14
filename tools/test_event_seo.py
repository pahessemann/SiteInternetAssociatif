import json
import re
import sqlite3
import unittest
from unittest.mock import patch

import app


class EventSeoTests(unittest.TestCase):
    def test_public_pages_publish_free_admission_and_association_performer(self):
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        self.addCleanup(database.close)
        database.executescript("""
            CREATE TABLE events (
                id INTEGER, title TEXT, starts_on TEXT, ends_on TEXT,
                start_time TEXT, end_time TEXT, location TEXT, address TEXT,
                image_url TEXT, description TEXT, created_at TEXT
            );
            CREATE TABLE articles (published INTEGER, featured INTEGER, created_at TEXT);
            CREATE TABLE photos (visibility TEXT, created_at TEXT);
            INSERT INTO events VALUES (
                1, 'Atelier semis', '2099-04-10', NULL, '14:00', '16:00',
                'Jardin Vert-Tige', 'Paris 14', '/static/hero-garden.png',
                'Un atelier au jardin.', '2099-01-01'
            );
            INSERT INTO events VALUES (
                2, 'Rencontre au jardin', '2099-05-10', NULL, '', '',
                '', '', '', 'Rencontre avec les jardiniers.', '2099-01-01'
            );
        """)
        settings = dict(app.DEFAULT_SETTINGS, site_title='Jardin Vert-Tige & amis')
        with (
            patch.object(app, 'connect', return_value=database),
            patch.object(app, 'read_settings', return_value=settings),
            patch.object(app, 'PUBLIC_URL', 'https://jardin-vert-tige.fr'),
            patch.object(app, 'christmas_nav_enabled', return_value=False),
        ):
            for page in (app.home_page, lambda: app.agenda_page({})):
                with self.subTest(page=page):
                    body = page()
                    schemas = [json.loads(payload) for payload in re.findall(
                        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', body
                    )]
                    events = [schema for schema in schemas if schema.get('@type') == 'Event']
                    self.assertEqual(len(events), 2)
                    for event in events:
                        self.assertTrue(event['isAccessibleForFree'])
                        self.assertEqual(event['offers']['@type'], 'Offer')
                        self.assertEqual(event['offers']['price'], 0)
                        self.assertEqual(event['offers']['priceCurrency'], 'EUR')
                        self.assertEqual(event['performer']['@type'], 'Organization')
                        self.assertEqual(event['performer']['name'], settings['site_title'])
                        self.assertEqual(event['performer']['url'], 'https://jardin-vert-tige.fr')
                    self.assertEqual(events[0]['startDate'], '2099-04-10T14:00:00')
                    self.assertEqual(events[1]['startDate'], '2099-05-10')


if __name__ == '__main__':
    unittest.main()
