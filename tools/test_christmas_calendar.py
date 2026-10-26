from datetime import date
import sqlite3
import unittest
from unittest.mock import Mock, patch

import app


class ChristmasCalendarTests(unittest.TestCase):
    def setUp(self):
        self.database = sqlite3.connect(":memory:")
        self.database.row_factory = sqlite3.Row
        self.addCleanup(self.database.close)
        self.database.executescript(
            """
            CREATE TABLE christmas_calendars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL UNIQUE,
                eyebrow TEXT,
                title TEXT NOT NULL,
                intro TEXT,
                image_url TEXT,
                accent_color TEXT NOT NULL,
                layout_variant INTEGER NOT NULL,
                completion_enabled INTEGER NOT NULL DEFAULT 1,
                completion_title TEXT NOT NULL DEFAULT 'Bravo, vous avez complété le calendrier !',
                completion_message TEXT NOT NULL DEFAULT 'Vous avez découvert les 24 surprises du jardin.',
                completion_link_label TEXT NOT NULL DEFAULT 'Découvrir la surprise',
                completion_link_url TEXT,
                published INTEGER NOT NULL,
                show_in_nav INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE christmas_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calendar_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                teaser TEXT,
                body TEXT,
                image_url TEXT,
                link_url TEXT,
                link_label TEXT,
                enabled INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(calendar_id, day_number)
            );
            INSERT INTO christmas_calendars
                (year, eyebrow, title, intro, image_url, accent_color, layout_variant,
                 published, show_in_nav, created_at, updated_at)
            VALUES
                (2026, '24 jours', 'Noël au jardin', 'Une surprise par jour.',
                 '/static/hero-garden.png', '#a62f2f', 3, 1, 1, '2026-10-01', '2026-10-01');
            """
        )
        app.populate_christmas_days(self.database, 1)
        for mock in (
            patch.object(app, "connect", return_value=self.database),
            patch.object(app, "read_settings", return_value=dict(app.DEFAULT_SETTINGS)),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def test_public_calendar_opens_only_the_current_day_before_christmas(self):
        page = app.christmas_calendar_page(2026, today=date(2026, 12, 5))
        self.assertIsNotNone(page)
        self.assertEqual(page.count(' data-christmas-day="'), 5)
        self.assertEqual(page.count("is-open is-covered"), 1)
        self.assertEqual(page.count("is-locked is-covered is-past"), 4)
        self.assertIn("1 case disponible aujourd’hui", page)
        self.assertIn("Rattrapage le 25", page)
        self.assertIn("Si vous supprimez vos cookies", page)
        self.assertIn("christmas-puzzle-tab", page)
        self.assertEqual(page.count("christmas-piece-art"), 5)
        self.assertIn("puzzle-position-", page)
        self.assertIn(app.DEFAULT_CHRISTMAS_DAYS[4][1], page)
        self.assertNotIn(app.DEFAULT_CHRISTMAS_DAYS[5][1], page)

    def test_all_enabled_cases_open_for_catch_up_from_december_25(self):
        page = app.christmas_calendar_page(2026, today=date(2026, 12, 25))
        self.assertIsNotNone(page)
        self.assertEqual(page.count(' data-christmas-day="'), 24)
        self.assertEqual(page.count("is-open is-covered"), 24)
        self.assertNotIn("is-past", page)
        self.assertIn("24 cases disponibles aujourd’hui", page)

    def test_draft_is_private_but_available_in_admin_preview(self):
        self.database.execute("UPDATE christmas_calendars SET published = 0 WHERE id = 1")
        self.assertIsNone(app.christmas_calendar_page(2026, today=date(2026, 12, 24)))
        preview = app.christmas_calendar_page(
            today=date(2026, 12, 24), preview_calendar_id=1
        )
        self.assertIsNotNone(preview)
        self.assertEqual(preview.count(' data-christmas-day="'), 1)
        self.assertEqual(preview.count("christmas-piece-art"), 1)
        self.assertIn("Mode test", preview)
        self.assertIn("Case manquée, disponible au rattrapage le 25 décembre", preview)
        self.assertIn('content="noindex, nofollow"', preview)
        self.assertNotIn("data-christmas-progress-notice", preview)
        self.assertNotIn("data-cookie-banner", preview)

    def test_public_calendar_is_hidden_outside_december(self):
        self.assertFalse(app.christmas_public_window(date(2026, 11, 30)))
        self.assertTrue(app.christmas_public_window(date(2026, 12, 1)))
        self.assertTrue(app.christmas_public_window(date(2026, 12, 31)))
        self.assertFalse(app.christmas_public_window(date(2027, 1, 1)))
        self.assertIsNone(app.christmas_calendar_page(2026, today=date(2026, 11, 30)))

    def test_admin_can_unlock_every_case_outside_december(self):
        preview = app.christmas_calendar_page(
            today=date(2026, 10, 26),
            preview_calendar_id=1,
            preview_unlock_all=True,
        )
        self.assertEqual(preview.count(' data-christmas-day="'), 24)
        self.assertIn("Mode test · toutes les cases déverrouillées", preview)
        self.assertIn('data-christmas-preview="1"', preview)

    def test_copying_an_edition_creates_an_unpublished_new_year(self):
        handler = object.__new__(app.VertTigeHandler)
        handler.read_form = Mock(
            return_value=({"year": "2027", "source_calendar_id": "1"}, {})
        )
        handler.redirect = Mock()

        handler.create_christmas_calendar()

        copied = self.database.execute(
            "SELECT * FROM christmas_calendars WHERE year = 2027"
        ).fetchone()
        self.assertIsNotNone(copied)
        self.assertEqual(copied["published"], 0)
        self.assertEqual(copied["layout_variant"], 4)
        self.assertEqual(copied["completion_enabled"], 1)
        self.assertEqual(copied["completion_title"], "Bravo, vous avez complété le calendrier !")
        days = self.database.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = ? ORDER BY day_number",
            (copied["id"],),
        ).fetchall()
        self.assertEqual(len(days), 24)
        self.assertEqual(days[0]["body"], app.DEFAULT_CHRISTMAS_DAYS[0][3])
        handler.redirect.assert_called_once_with(
            f"/admin/noel/{copied['id']}?status=duplicate"
        )

    def test_disabled_day_stays_closed_in_preview(self):
        self.database.execute(
            "UPDATE christmas_days SET enabled = 0 WHERE calendar_id = 1 AND day_number = 3"
        )
        page = app.christmas_calendar_page(
            today=date(2026, 12, 24), preview_calendar_id=1, preview_unlock_all=True
        )
        self.assertEqual(page.count(' data-christmas-day="'), 23)
        self.assertIn("Case 3, Case désactivée", page)

    def test_puzzle_layout_is_stable_shuffled_and_configurable(self):
        positions = app.christmas_door_positions(2026, 3)
        self.assertEqual(sorted(positions), list(range(1, 25)))
        self.assertNotEqual(positions, list(range(1, 25)))
        self.assertEqual(positions, app.christmas_door_positions(2026, 3))
        self.assertNotEqual(positions, app.christmas_door_positions(2026, 4))

    def test_every_cut_template_layout_maps_all_days_once(self):
        for variant in range(1, 13):
            positions = app.christmas_door_positions(2026, variant)
            day_by_position = {
                position: day_number
                for day_number, position in enumerate(positions, start=1)
            }
            self.assertEqual(sorted(day_by_position), list(range(1, 25)))
            self.assertEqual(sorted(day_by_position.values()), list(range(1, 25)))

    def test_jigsaw_overlay_has_continuous_curved_boundaries(self):
        vertical, horizontal = app.christmas_puzzle_path_data(2026, 3)
        self.assertEqual(vertical.count("M"), 20)
        self.assertEqual(horizontal.count("M"), 18)
        self.assertIn("C", vertical)
        self.assertIn("C", horizontal)
        overlay = app.christmas_puzzle_overlay_svg(2026, 3)
        self.assertIn('viewBox="0 0 600 400"', overlay)
        self.assertIn("christmas-puzzle-outline", overlay)

    def test_each_calendar_piece_gets_a_matching_clip_path(self):
        clips = app.christmas_puzzle_clip_definitions(2026, 3)
        self.assertEqual(clips.count("<clipPath"), 24)
        self.assertIn('id="christmas-piece-1"', clips)
        self.assertIn('id="christmas-piece-24"', clips)
        middle_piece = app.christmas_piece_clip_path_data(2026, 3, 8)
        self.assertTrue(middle_piece.startswith("M"))
        self.assertTrue(middle_piece.endswith("Z"))
        self.assertGreaterEqual(middle_piece.count("C"), 4)

    def test_completion_reward_is_only_eligible_on_december_24(self):
        page_24 = app.christmas_calendar_page(
            today=date(2026, 12, 24), preview_calendar_id=1, preview_unlock_all=True
        )
        self.assertIn('data-christmas-completion-eligible="1"', page_24)
        self.assertIn("data-christmas-completion-modal", page_24)
        self.assertIn("Voir ma récompense", page_24)

        page_25 = app.christmas_calendar_page(
            today=date(2026, 12, 25), preview_calendar_id=1, preview_unlock_all=True
        )
        self.assertIn('data-christmas-completion-eligible="0"', page_25)

    def test_admin_can_update_edition_and_day_content(self):
        handler = object.__new__(app.VertTigeHandler)
        handler.redirect = Mock()
        handler.read_form = Mock(
            return_value=(
                {
                    "eyebrow": "Décembre au jardin",
                    "title": "Notre Avent 2026",
                    "intro": "Une édition entièrement personnalisée.",
                    "accent_color": "#235d42",
                    "layout_variant": "7",
                    "completion_enabled": "1",
                    "completion_title": "Bravo du jardin !",
                    "completion_message": "Présentez cet écran au jardin pour recevoir votre surprise.",
                    "completion_link_label": "Voir les modalités",
                    "completion_link_url": "https://example.org/cadeau",
                    "published": "1",
                    "show_in_nav": "1",
                    "image_choice": "",
                },
                {},
            )
        )
        handler.save_christmas_calendar(1)
        calendar = self.database.execute(
            "SELECT * FROM christmas_calendars WHERE id = 1"
        ).fetchone()
        self.assertEqual(calendar["title"], "Notre Avent 2026")
        self.assertEqual(calendar["accent_color"], "#235d42")
        self.assertEqual(calendar["layout_variant"], 7)
        self.assertEqual(calendar["completion_title"], "Bravo du jardin !")
        self.assertEqual(calendar["completion_link_url"], "https://example.org/cadeau")

        handler.read_form = Mock(
            return_value=(
                {
                    "category": "atelier",
                    "title": "Une nouvelle surprise",
                    "teaser": "À fabriquer ensemble.",
                    "body": "Le contenu personnalisé de la case.",
                    "link_url": "https://example.org/atelier",
                    "link_label": "Voir l’atelier",
                    "enabled": "1",
                    "image_choice": "",
                },
                {},
            )
        )
        handler.save_christmas_day(1, 7)
        day = self.database.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = 1 AND day_number = 7"
        ).fetchone()
        self.assertEqual(day["category"], "atelier")
        self.assertEqual(day["title"], "Une nouvelle surprise")
        self.assertEqual(day["link_label"], "Voir l’atelier")


if __name__ == "__main__":
    unittest.main()
