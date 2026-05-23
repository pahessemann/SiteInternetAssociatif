from __future__ import annotations

import calendar
import base64
import binascii
import hashlib
import hmac
import html
import mimetypes
import os
import re
import secrets
import smtplib
import sqlite3
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as email_policy
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = STATIC_DIR / "uploads"
DB_PATH = DATA_DIR / "vert_tige.sqlite3"
LOG_PATH = BASE_DIR / "server.log"

HOST = os.getenv("VERT_TIGE_HOST", "127.0.0.1")
PORT = int(os.getenv("VERT_TIGE_PORT", "8000"))
ADMIN_PASSWORD = os.getenv("VERT_TIGE_ADMIN_PASSWORD", "jardin")
SESSION_SECRET = os.getenv("VERT_TIGE_SECRET", "change-this-secret-before-production")
SESSION_COOKIE = "vert_tige_session"
SESSION_MAX_AGE_SECONDS = int(os.getenv("VERT_TIGE_SESSION_SECONDS", str(12 * 60 * 60)))
PASSWORD_ITERATIONS = 390_000
ROLE_LABELS = {
    "owner": "Référent",
    "admin": "Administrateur",
}

SMTP_HOST = os.getenv("VERT_TIGE_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("VERT_TIGE_SMTP_PORT", "587"))
SMTP_USER = os.getenv("VERT_TIGE_SMTP_USER", "")
SMTP_PASSWORD = os.getenv("VERT_TIGE_SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("VERT_TIGE_SMTP_FROM", "site@vert-tige.local")
CONTACT_TO = os.getenv("VERT_TIGE_CONTACT_EMAIL", "")

MONTHS = [
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
WEEKDAYS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PHOTO_VISIBILITY_LABELS = {
    "gallery": "Galerie uniquement",
    "article": "Articles uniquement",
    "both": "Galerie + articles",
}

DEFAULT_SETTINGS = {
    "site_title": "Vert-Tige",
    "tagline": "Jardin partagé à Paris 14",
    "home_intro": (
        "Vert-Tige est un jardin partagé du 14e arrondissement : un lieu pour "
        "cultiver, transmettre, bricoler, composter et créer des rencontres de quartier."
    ),
    "contact_email": "contact@vert-tige.local",
    "logo_url": "",
}


@dataclass
class Upload:
    filename: str
    content_type: str
    data: bytes


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_log(message: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass
    try:
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError:
        pass


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return slug or "article"


def unique_slug(conn: sqlite3.Connection, title: str, article_id: int | None = None) -> str:
    base = slugify(title)
    candidate = base
    index = 2
    while True:
        if article_id:
            row = conn.execute(
                "SELECT id FROM articles WHERE slug = ? AND id != ?",
                (candidate, article_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT id FROM articles WHERE slug = ?", (candidate,)).fetchone()
        if row is None:
            return candidate
        candidate = f"{base}-{index}"
        index += 1


def e(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def paragraphs(value: str | None) -> str:
    blocks = [block.strip() for block in (value or "").split("\n\n") if block.strip()]
    if not blocks:
        return ""
    return "".join(f"<p>{e(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = date.fromisoformat(value)
        return f"{parsed.day} {MONTHS[parsed.month]} {parsed.year}"
    except ValueError:
        return e(value)


def format_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.strftime("%Hh%M").replace("h00", "h")
    except ValueError:
        return e(value)


def valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value or ""))


def valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def valid_time(value: str) -> bool:
    if not value:
        return True
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def event_schedule(row: sqlite3.Row) -> str:
    end_date = f" au {format_date(row['ends_on'])}" if row["ends_on"] else ""
    start_time = format_time(row["start_time"])
    end_time = format_time(row["end_time"])
    if start_time and end_time:
        time_text = f" · {start_time}-{end_time}"
    elif start_time:
        time_text = f" · {start_time}"
    else:
        time_text = ""
    return f"{format_date(row['starts_on'])}{end_date}{time_text}"


def event_place(row: sqlite3.Row) -> str:
    location = row["location"] or "Jardin Vert-Tige"
    address = row["address"] or ""
    if address:
        return f"{location} · {address}"
    return location


def normalize_photo_visibility(value: str | None, default: str = "both") -> str:
    candidate = (value or default).strip()
    if candidate in PHOTO_VISIBILITY_LABELS:
        return candidate
    return default


def photo_visibility_label(value: str | None) -> str:
    return PHOTO_VISIBILITY_LABELS[normalize_photo_visibility(value)]


def photo_visibility_options(selected: str | None, default: str = "both") -> str:
    current = normalize_photo_visibility(selected, default)
    return "".join(
        f'<option value="{key}" {"selected" if key == current else ""}>{e(label)}</option>'
        for key, label in PHOTO_VISIBILITY_LABELS.items()
    )


def calendar_event_chip(row: sqlite3.Row) -> str:
    time_text = format_time(row["start_time"])
    time_html = f"<span>{e(time_text)}</span>" if time_text else ""
    return f'<a href="#event-{row["id"]}">{time_html}{e(row["title"])}</a>'


def normalize_role(value: str | None, default: str = "admin") -> str:
    candidate = (value or default).strip()
    if candidate in ROLE_LABELS:
        return candidate
    return default


def role_label(value: str | None) -> str:
    return ROLE_LABELS[normalize_role(value)]


def role_options(selected: str | None = "admin") -> str:
    current = normalize_role(selected)
    return "".join(
        f'<option value="{key}" {"selected" if key == current else ""}>{e(label)}</option>'
        for key, label in ROLE_LABELS.items()
    )


def normalize_username(value: str | None) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "", (value or "").strip().lower())[:32]


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return salt, digest


def verify_password(user: sqlite3.Row, password: str) -> bool:
    _, digest = hash_password(password, user["password_salt"])
    return secrets.compare_digest(digest, user["password_hash"])


def read_settings() -> dict[str, str]:
    settings = dict(DEFAULT_SETTINGS)
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    settings.update({row["key"]: row["value"] for row in rows})
    return settings


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                starts_on TEXT NOT NULL,
                ends_on TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                address TEXT,
                description TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                summary TEXT,
                body TEXT,
                image_url TEXT,
                featured INTEGER NOT NULL DEFAULT 0,
                published INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                caption TEXT,
                visibility TEXT NOT NULL DEFAULT 'both',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                body TEXT NOT NULL,
                handled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        ensure_columns(
            conn,
            "events",
            {
                "start_time": "TEXT",
                "end_time": "TEXT",
                "address": "TEXT",
            },
        )
        ensure_columns(
            conn,
            "photos",
            {
                "visibility": "TEXT NOT NULL DEFAULT 'both'",
            },
        )
        conn.execute(
            "UPDATE photos SET visibility = 'both' WHERE visibility IS NULL OR visibility = ''"
        )
        user_count = conn.execute("SELECT COUNT(*) AS count FROM admin_users").fetchone()["count"]
        if user_count == 0:
            salt, password_hash = hash_password(ADMIN_PASSWORD)
            created = now_iso()
            conn.execute(
                """
                INSERT INTO admin_users
                    (username, display_name, role, password_salt, password_hash, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "admin",
                    "Administrateur référent",
                    "owner",
                    salt,
                    password_hash,
                    1,
                    created,
                    created,
                ),
            )
        conn.execute(
            """
            UPDATE events
            SET start_time = '10:00', end_time = '12:00', address = COALESCE(NULLIF(address, ''), 'Paris 14')
            WHERE title = 'Atelier compost' AND COALESCE(start_time, '') = ''
            """
        )
        conn.execute(
            """
            UPDATE events
            SET start_time = '09:30', end_time = '12:30', address = COALESCE(NULLIF(address, ''), 'Paris 14')
            WHERE title = 'Matinée plantations' AND COALESCE(start_time, '') = ''
            """
        )
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        article_count = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"]
        if article_count == 0:
            created = now_iso()
            conn.executemany(
                """
                INSERT INTO articles
                    (title, slug, summary, body, image_url, featured, published, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Bienvenue au jardin Vert-Tige",
                        "bienvenue-au-jardin-vert-tige",
                        "Une première note pour présenter l’esprit du jardin partagé.",
                        (
                            "Ce site servira de carnet de bord pour l’association : annonces, "
                            "photos, rendez-vous et nouvelles du jardin.\n\n"
                            "L’équipe pourra publier des articles simples, les mettre en avant "
                            "sur la page d’accueil et garder une trace des moments importants."
                        ),
                        "/static/hero-garden.png",
                        1,
                        1,
                        created,
                        created,
                    ),
                    (
                        "Préparer les semis du printemps",
                        "preparer-les-semis-du-printemps",
                        "Quelques idées d’ateliers à organiser avec les adhérents.",
                        (
                            "Un article peut contenir plusieurs paragraphes. Cette base reste volontairement "
                            "simple : un titre, un résumé, une image facultative et un texte principal."
                        ),
                        "/static/hero-garden.png",
                        0,
                        1,
                        created,
                        created,
                    ),
                ],
            )

        event_count = conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"]
        if event_count == 0:
            today = date.today()
            conn.executemany(
                """
                INSERT INTO events
                    (title, starts_on, ends_on, start_time, end_time, location, address, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "Atelier compost",
                        (today + timedelta(days=7)).isoformat(),
                        "",
                        "10:00",
                        "12:00",
                        "Jardin Vert-Tige",
                        "Paris 14",
                        "Point collectif sur le compost, les apports et les bons gestes à transmettre.",
                        now_iso(),
                    ),
                    (
                        "Matinée plantations",
                        (today + timedelta(days=18)).isoformat(),
                        "",
                        "09:30",
                        "12:30",
                        "Parcelles communes",
                        "Paris 14",
                        "Plantations de saison et entretien des bacs partagés.",
                        now_iso(),
                    ),
                ],
            )


def nav_link(path: str, label: str, current: str) -> str:
    active = " is-active" if current == path or (path != "/" and current.startswith(path)) else ""
    return f'<a class="nav-link{active}" href="{path}">{label}</a>'


def layout(title: str, body: str, current_path: str = "/") -> str:
    settings = read_settings()
    site_title = settings["site_title"]
    logo_url = settings.get("logo_url", "")
    brand_mark = (
        f'<img class="brand-logo" src="{e(logo_url)}" alt="">'
        if logo_url
        else '<span class="brand-mark">VT</span>'
    )
    nav = "".join(
        [
            nav_link("/", "Accueil", current_path),
            nav_link("/agenda", "Agenda", current_path),
            nav_link("/articles", "Articles", current_path),
            nav_link("/galerie", "Photos", current_path),
            nav_link("/contact", "Contact", current_path),
        ]
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)} · {e(site_title)}</title>
  <link rel="stylesheet" href="/static/styles.css">
  <script src="/static/article-editor.js" defer></script>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/">
      {brand_mark}
      <span><strong>{e(site_title)}</strong><small>{e(settings["tagline"])}</small></span>
    </a>
    <nav class="main-nav" aria-label="Navigation principale">{nav}</nav>
  </header>
  <main>{body}</main>
  <footer class="site-footer">
    <div>
      <strong>{e(site_title)}</strong>
      <span>{e(settings["tagline"])}</span>
    </div>
    <a href="/admin">Administration</a>
  </footer>
</body>
</html>"""


def article_card(row: sqlite3.Row) -> str:
    image = row["image_url"] or "/static/hero-garden.png"
    return f"""
    <article class="card article-card">
      <a href="/articles/{quote(row['slug'])}" class="media-link">
        <img src="{e(image)}" alt="">
      </a>
      <div class="card-body">
        <p class="meta">{format_date(row["created_at"][:10])}</p>
        <h3><a href="/articles/{quote(row['slug'])}">{e(row["title"])}</a></h3>
        <p>{e(row["summary"] or "")}</p>
      </div>
    </article>"""


def event_card(row: sqlite3.Row) -> str:
    return f"""
    <article class="card event-card" id="event-{row['id']}">
      <div class="date-badge"><strong>{date.fromisoformat(row["starts_on"]).day}</strong><span>{MONTHS[date.fromisoformat(row["starts_on"]).month][:3]}</span></div>
      <div>
        <p class="meta">{event_schedule(row)}</p>
        <h3>{e(row["title"])}</h3>
        <p class="place">{e(event_place(row))}</p>
        {paragraphs(row["description"])}
      </div>
    </article>"""


def home_page() -> str:
    settings = read_settings()
    today = date.today().isoformat()
    with connect() as conn:
        events = conn.execute(
            "SELECT * FROM events WHERE starts_on >= ? ORDER BY starts_on, start_time LIMIT 3",
            (today,),
        ).fetchall()
        articles = conn.execute(
            "SELECT * FROM articles WHERE published = 1 AND featured = 1 ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        photos = conn.execute(
            "SELECT * FROM photos WHERE visibility IN ('gallery', 'both') ORDER BY created_at DESC LIMIT 6"
        ).fetchall()

    event_html = "".join(event_card(row) for row in events) or empty_state(
        "Aucun rendez-vous à venir pour le moment."
    )
    article_html = "".join(article_card(row) for row in articles) or empty_state(
        "Les articles mis en avant apparaîtront ici."
    )
    photo_html = render_photo_strip(photos)

    body = f"""
    <section class="hero">
      <div class="hero-content">
        <p class="eyebrow">Jardin partagé · Paris 14</p>
        <h1>{e(settings["site_title"])}</h1>
        <p>{e(settings["home_intro"])}</p>
        <div class="button-row">
          <a class="button primary" href="/agenda">Voir l’agenda</a>
          <a class="button secondary" href="/contact">Contacter l’association</a>
        </div>
      </div>
    </section>

    <section class="section split">
      <div>
        <p class="eyebrow">Association de quartier</p>
        <h2>Un site pour faire vivre le jardin entre deux permanences</h2>
      </div>
      <div class="lead">
        {paragraphs(settings["home_intro"])}
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Prochains rendez-vous</p>
          <h2>Agenda du jardin</h2>
        </div>
        <a class="text-link" href="/agenda">Tout voir</a>
      </div>
      <div class="card-grid">{event_html}</div>
    </section>

    <section class="section muted-band">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Carnet de bord</p>
          <h2>Articles mis en avant</h2>
        </div>
        <a class="text-link" href="/articles">Tous les articles</a>
      </div>
      <div class="card-grid">{article_html}</div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Banque de photos</p>
          <h2>Images du jardin</h2>
        </div>
        <a class="text-link" href="/galerie">Ouvrir la galerie</a>
      </div>
      {photo_html}
    </section>
    """
    return layout("Accueil", body, "/")


def empty_state(message: str) -> str:
    return f'<div class="empty-state">{e(message)}</div>'


def render_photo_strip(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return """
        <div class="photo-preview">
          <img src="/static/hero-garden.png" alt="">
          <div>
            <h3>La galerie est prête</h3>
            <p>Les premières photos ajoutées depuis l’administration apparaîtront ici.</p>
          </div>
        </div>
        """
    items = "".join(
        f"""
        <figure class="photo-tile">
          <img src="/static/uploads/{e(row['filename'])}" alt="{e(row['title'] or 'Photo du jardin')}">
          <figcaption>{e(row['title'] or row['caption'] or 'Photo du jardin')}</figcaption>
        </figure>
        """
        for row in rows
    )
    return f'<div class="photo-grid compact">{items}</div>'


def parse_month(query: dict[str, list[str]]) -> date:
    raw = query.get("mois", [date.today().strftime("%Y-%m")])[0]
    try:
        year, month = raw.split("-", 1)
        return date(int(year), int(month), 1)
    except (ValueError, TypeError):
        today = date.today()
        return date(today.year, today.month, 1)


def add_month(value: date, delta: int) -> date:
    month = value.month + delta
    year = value.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1)


def render_calendar_month(current: date, events: list[sqlite3.Row]) -> str:
    events_by_day: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for event in events:
        try:
            starts = date.fromisoformat(event["starts_on"])
        except ValueError:
            continue
        if starts.year == current.year and starts.month == current.month:
            events_by_day[starts.day].append(event)

    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(current.year, current.month)
    head = "".join(f"<span>{day}</span>" for day in WEEKDAYS)
    rows = []
    for week in weeks:
        cells = []
        for day in week:
            muted = " muted" if day.month != current.month else ""
            chips = "".join(
                calendar_event_chip(event)
                for event in events_by_day.get(day.day, [])
                if day.month == current.month
            )
            cells.append(
                f"""
                <div class="calendar-cell{muted}">
                  <span class="day-number">{day.day}</span>
                  <div class="calendar-events">{chips}</div>
                </div>
                """
            )
        rows.append(f'<div class="calendar-row">{"".join(cells)}</div>')
    return f'<div class="calendar"><div class="calendar-weekdays">{head}</div>{"".join(rows)}</div>'


def agenda_page(query: dict[str, list[str]]) -> str:
    current = parse_month(query)
    start = current.isoformat()
    next_month = add_month(current, 1)
    month_end = (next_month - timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    with connect() as conn:
        month_events = conn.execute(
            "SELECT * FROM events WHERE starts_on BETWEEN ? AND ? ORDER BY starts_on, start_time",
            (start, month_end),
        ).fetchall()
        upcoming = conn.execute(
            "SELECT * FROM events WHERE starts_on >= ? ORDER BY starts_on, start_time LIMIT 20",
            (today,),
        ).fetchall()

    prev_link = add_month(current, -1).strftime("%Y-%m")
    next_link = add_month(current, 1).strftime("%Y-%m")
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Calendrier</p>
      <h1>Agenda du jardin</h1>
      <p>Les ateliers, permanences et moments collectifs de Vert-Tige.</p>
    </section>
    <section class="section">
      <div class="calendar-toolbar">
        <a class="button secondary" href="/agenda?mois={prev_link}">Mois précédent</a>
        <h2>{MONTHS[current.month].capitalize()} {current.year}</h2>
        <a class="button secondary" href="/agenda?mois={next_link}">Mois suivant</a>
      </div>
      {render_calendar_month(current, month_events)}
    </section>
    <section class="section muted-band">
      <div class="section-heading">
        <div>
          <p class="eyebrow">À venir</p>
          <h2>Prochains événements</h2>
        </div>
      </div>
      <div class="list-stack">{"".join(event_card(row) for row in upcoming) or empty_state("Aucun événement à venir.")}</div>
    </section>
    """
    return layout("Agenda", body, "/agenda")


def articles_page() -> str:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE published = 1 ORDER BY created_at DESC"
        ).fetchall()
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Articles</p>
      <h1>Carnet de bord</h1>
      <p>Actualités, récits d’ateliers et nouvelles du jardin partagé.</p>
    </section>
    <section class="section">
      <div class="card-grid">{"".join(article_card(row) for row in rows) or empty_state("Aucun article publié.")}</div>
    </section>
    """
    return layout("Articles", body, "/articles")


def article_page(slug: str) -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM articles WHERE slug = ? AND published = 1",
            (slug,),
        ).fetchone()
    if not row:
        return not_found_page()
    image = row["image_url"] or "/static/hero-garden.png"
    body = f"""
    <article class="article-page">
      <header class="article-header">
        <p class="eyebrow">{format_date(row["created_at"][:10])}</p>
        <h1>{e(row["title"])}</h1>
        <p>{e(row["summary"] or "")}</p>
      </header>
      <img class="article-cover" src="{e(image)}" alt="">
      <div class="article-body">{paragraphs(row["body"])}</div>
    </article>
    """
    return layout(row["title"], body, "/articles")


def gallery_page() -> str:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE visibility IN ('gallery', 'both') ORDER BY created_at DESC"
        ).fetchall()
    if rows:
        items = "".join(
            f"""
            <figure class="photo-tile">
              <img src="/static/uploads/{e(row['filename'])}" alt="{e(row['title'] or 'Photo du jardin')}">
              <figcaption>
                <strong>{e(row['title'] or 'Photo du jardin')}</strong>
                <span>{e(row['caption'] or '')}</span>
              </figcaption>
            </figure>
            """
            for row in rows
        )
    else:
        items = """
        <figure class="photo-tile wide">
          <img src="/static/hero-garden.png" alt="">
          <figcaption><strong>Galerie en préparation</strong><span>Ajoute les premières photos depuis l’administration.</span></figcaption>
        </figure>
        """
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Photos</p>
      <h1>Banque de photos</h1>
      <p>Un espace pour conserver et partager les images du jardin.</p>
    </section>
    <section class="section">
      <div class="photo-grid">{items}</div>
    </section>
    """
    return layout("Photos", body, "/galerie")


def contact_page(sent: bool = False) -> str:
    settings = read_settings()
    success = (
        '<div class="notice success">Message envoyé. Il est aussi conservé dans l’administration.</div>'
        if sent
        else ""
    )
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Contact</p>
      <h1>Écrire à Vert-Tige</h1>
      <p>Pour une question, une inscription ou une proposition d’atelier.</p>
    </section>
    <section class="section contact-layout">
      <div>
        <h2>Formulaire</h2>
        {success}
        <form class="form-panel" method="post" action="/contact">
          <label>Nom<input required name="name" autocomplete="name"></label>
          <label>Email<input required type="email" name="email" autocomplete="email"></label>
          <label>Sujet<input name="subject"></label>
          <label>Message<textarea required name="body" rows="7"></textarea></label>
          <button class="button primary" type="submit">Envoyer</button>
        </form>
      </div>
      <aside class="info-panel">
        <p class="eyebrow">Adresse de contact</p>
        <h3>{e(settings["contact_email"])}</h3>
        <p>Sans configuration SMTP, le formulaire enregistre les messages dans l’espace admin. Avec SMTP, il les envoie aussi par email.</p>
      </aside>
    </section>
    """
    return layout("Contact", body, "/contact")


def admin_shell(title: str, content: str, tab: str = "/admin") -> str:
    tabs = "".join(
        [
            nav_link("/admin", "Tableau de bord", tab),
            nav_link("/admin/home", "Accueil", tab),
            nav_link("/admin/events", "Agenda", tab),
            nav_link("/admin/articles", "Articles", tab),
            nav_link("/admin/photos", "Photos", tab),
            nav_link("/admin/messages", "Messages", tab),
            nav_link("/admin/users", "Comptes", tab),
        ]
    )
    body = f"""
    <section class="admin-shell">
      <div class="admin-heading">
        <div>
          <p class="eyebrow">Administration</p>
          <h1>{e(title)}</h1>
        </div>
        <a class="button secondary" href="/admin/logout">Déconnexion</a>
      </div>
      <nav class="admin-tabs">{tabs}</nav>
      {content}
    </section>
    """
    return layout(f"Admin - {title}", body, "/admin")


def login_page(error: bool = False) -> str:
    alert = '<div class="notice error">Identifiant ou mot de passe incorrect.</div>' if error else ""
    body = f"""
    <section class="login-screen">
      <form class="login-card" method="post" action="/admin/login">
        <p class="eyebrow">Administration Vert-Tige</p>
        <h1>Connexion</h1>
        {alert}
        <label>Identifiant<input name="username" value="admin" autocomplete="username" required autofocus></label>
        <label>Mot de passe<input type="password" name="password" required autocomplete="current-password"></label>
        <button class="button primary" type="submit">Entrer</button>
        <p class="form-note">Compte référent de départ : <code>admin</code> / <code>jardin</code>.</p>
      </form>
    </section>
    """
    return layout("Connexion admin", body, "/admin")


def admin_dashboard() -> str:
    with connect() as conn:
        counts = {
            "articles": conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()["count"],
            "events": conn.execute("SELECT COUNT(*) AS count FROM events").fetchone()["count"],
            "photos": conn.execute("SELECT COUNT(*) AS count FROM photos").fetchone()["count"],
            "messages": conn.execute(
                "SELECT COUNT(*) AS count FROM messages WHERE handled = 0"
            ).fetchone()["count"],
        }
    cards = "".join(
        f'<div class="metric"><strong>{value}</strong><span>{label}</span></div>'
        for label, value in [
            ("articles", counts["articles"]),
            ("événements", counts["events"]),
            ("photos", counts["photos"]),
            ("messages à traiter", counts["messages"]),
        ]
    )
    content = f"""
    <div class="metrics">{cards}</div>
    <div class="admin-grid">
      <a class="admin-action" href="/admin/home"><strong>Page d’accueil</strong><span>Modifier le texte principal et l’email de contact.</span></a>
      <a class="admin-action" href="/admin/events/new"><strong>Nouvel événement</strong><span>Ajouter un atelier ou une permanence au calendrier.</span></a>
      <a class="admin-action" href="/admin/articles/new"><strong>Nouvel article</strong><span>Rédiger une actualité et choisir si elle est mise en avant.</span></a>
      <a class="admin-action" href="/admin/photos"><strong>Ajouter des photos</strong><span>Alimenter la banque d’images du jardin.</span></a>
    </div>
    <div class="notice warning">Avant une mise en ligne publique, remplace le mot de passe du compte référent, crée les comptes personnels nécessaires et configure <code>VERT_TIGE_SECRET</code>.</div>
    """
    return admin_shell("Tableau de bord", content, "/admin")


def admin_home_page() -> str:
    settings = read_settings()
    logo_preview = (
        f'<img class="logo-preview" src="{e(settings.get("logo_url"))}" alt="Logo actuel">'
        if settings.get("logo_url")
        else '<div class="logo-placeholder">VT</div>'
    )
    content = f"""
    <form class="form-panel" method="post" action="/admin/home" enctype="multipart/form-data">
      <label>Nom du site<input name="site_title" value="{e(settings['site_title'])}" required></label>
      <label>Sous-titre<input name="tagline" value="{e(settings['tagline'])}" required></label>
      <label>Email affiché<input type="email" name="contact_email" value="{e(settings['contact_email'])}"></label>
      <div class="logo-editor">
        <div>
          <p class="field-label">Logo actuel</p>
          {logo_preview}
        </div>
        <div>
          <label>Nouveau logo<input type="file" name="logo_file" accept="image/*"></label>
          <label class="inline-check"><input type="checkbox" name="remove_logo" value="1"> Revenir au monogramme VT</label>
        </div>
      </div>
      <label>Texte d’accueil<textarea name="home_intro" rows="7">{e(settings['home_intro'])}</textarea></label>
      <button class="button primary" type="submit">Enregistrer</button>
    </form>
    """
    return admin_shell("Page d’accueil", content, "/admin/home")


def event_form(row: sqlite3.Row | None = None) -> str:
    action = "/admin/events/save" if row is None else f"/admin/events/{row['id']}/save"
    title = row["title"] if row else ""
    starts = row["starts_on"] if row else date.today().isoformat()
    ends = row["ends_on"] if row else ""
    start_time = row["start_time"] if row else ""
    end_time = row["end_time"] if row else ""
    location = row["location"] if row else "Jardin Vert-Tige"
    address = row["address"] if row else ""
    description = row["description"] if row else ""
    return f"""
    <form class="form-panel" method="post" action="{action}">
      <label>Titre<input name="title" value="{e(title)}" required></label>
      <div class="form-row">
        <label>Date de début<input type="date" name="starts_on" value="{e(starts)}" required></label>
        <label>Date de fin<input type="date" name="ends_on" value="{e(ends)}"></label>
      </div>
      <div class="form-row">
        <label>Heure de début<input type="time" name="start_time" value="{e(start_time)}"></label>
        <label>Heure de fin<input type="time" name="end_time" value="{e(end_time)}"></label>
      </div>
      <label>Lieu<input name="location" value="{e(location)}"></label>
      <label>Adresse<input name="address" value="{e(address)}" placeholder="Ex. 12 rue des Plantes, 75014 Paris"></label>
      <label>Description<textarea name="description" rows="6">{e(description)}</textarea></label>
      <button class="button primary" type="submit">Enregistrer</button>
    </form>
    """


def admin_events_page() -> str:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY starts_on DESC, start_time DESC").fetchall()
    table = "".join(
        f"""
        <tr>
          <td>{event_schedule(row)}</td>
          <td><strong>{e(row['title'])}</strong><span>{e(event_place(row))}</span></td>
          <td class="actions">
            <a class="button small secondary" href="/admin/events/{row['id']}/edit">Modifier</a>
            <form method="post" action="/admin/events/{row['id']}/delete"><button class="button small danger" type="submit">Supprimer</button></form>
          </td>
        </tr>
        """
        for row in rows
    )
    content = f"""
    <div class="admin-toolbar"><a class="button primary" href="/admin/events/new">Nouvel événement</a></div>
    <table class="admin-table">
      <thead><tr><th>Date</th><th>Événement</th><th></th></tr></thead>
      <tbody>{table or '<tr><td colspan="3">Aucun événement.</td></tr>'}</tbody>
    </table>
    """
    return admin_shell("Agenda", content, "/admin/events")


def admin_event_edit_page(event_id: int | None = None) -> str:
    row = None
    if event_id is not None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return not_found_page()
    title = "Nouvel événement" if row is None else "Modifier l’événement"
    return admin_shell(title, event_form(row), "/admin/events")


def article_form(row: sqlite3.Row | None = None) -> str:
    action = "/admin/articles/save" if row is None else f"/admin/articles/{row['id']}/save"
    title = row["title"] if row else ""
    summary = row["summary"] if row else ""
    body = row["body"] if row else ""
    image_url = (row["image_url"] if row else "") or "/static/hero-garden.png"
    featured = "checked" if row and row["featured"] else ""
    published = "checked" if row is None or row["published"] else ""
    with connect() as conn:
        photos = conn.execute(
            "SELECT * FROM photos WHERE visibility IN ('article', 'both') ORDER BY created_at DESC"
        ).fetchall()
    photo_options = "".join(
        f'<option value="/static/uploads/{e(photo["filename"])}">{e(photo["title"] or photo["filename"])}</option>'
        for photo in photos
    )
    current_preview = (
        f'<img class="cover-preview" src="{e(image_url)}" alt="Image de couverture actuelle">'
        if image_url
        else ""
    )
    return f"""
    <form class="form-panel editor article-editor" method="post" action="{action}" enctype="multipart/form-data" data-article-editor>
      <label>Titre<input name="title" value="{e(title)}" required></label>
      <label>Résumé<input name="summary" value="{e(summary)}"></label>
      <div class="image-picker">
        <div>
          <p class="field-label">Image de couverture</p>
          {current_preview}
          <button class="button small secondary crop-current-button" type="button" data-crop-current data-current-image="{e(image_url)}">Recadrer l’image actuelle</button>
        </div>
        <div class="image-picker-controls">
          <input type="hidden" name="current_image_url" value="{e(image_url)}">
          <input type="hidden" name="cropped_image_data" data-crop-output>
          <label>Choisir parmi les images disponibles pour les articles
            <select name="image_choice" data-crop-library>
              <option value="">Conserver l’image actuelle</option>
              <option value="/static/hero-garden.png">Visuel par défaut</option>
              {photo_options}
            </select>
          </label>
          <label>Ou envoyer une nouvelle image
            <input type="file" name="article_image" accept="image/*" data-crop-file>
          </label>
          <p class="form-note">Une image envoyée ici sera ajoutée automatiquement à la banque de photos avec la visibilité “Articles uniquement”.</p>
        </div>
      </div>
      <div class="crop-tool" data-crop-tool hidden>
        <div class="crop-canvas-wrap"><canvas data-crop-canvas></canvas></div>
        <div class="crop-controls">
          <label>Format
            <select name="image_aspect" data-crop-aspect>
              <option value="16:9">Paysage 16:9</option>
              <option value="4:3">Paysage 4:3</option>
              <option value="3:2">Photo 3:2</option>
              <option value="1:1">Carré 1:1</option>
              <option value="2:3">Portrait 2:3</option>
              <option value="original">Format original</option>
            </select>
          </label>
          <label>Zoom<input type="range" min="1" max="2.5" step="0.01" value="1" data-crop-zoom></label>
          <label>Horizontal<input type="range" min="0" max="100" step="1" value="50" data-crop-x></label>
          <label>Vertical<input type="range" min="0" max="100" step="1" value="50" data-crop-y></label>
        </div>
      </div>
      <label>Texte<textarea name="body" rows="12">{e(body)}</textarea></label>
      <div class="check-row">
        <label><input type="checkbox" name="published" value="1" {published}> Publié</label>
        <label><input type="checkbox" name="featured" value="1" {featured}> Mis en avant sur l’accueil</label>
      </div>
      <button class="button primary" type="submit">Enregistrer</button>
    </form>
    """


def admin_articles_page() -> str:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    table = "".join(
        f"""
        <tr>
          <td><strong>{e(row['title'])}</strong><span>/{e(row['slug'])}</span></td>
          <td>{'Oui' if row['published'] else 'Non'}</td>
          <td>{'Oui' if row['featured'] else 'Non'}</td>
          <td class="actions">
            <a class="button small secondary" href="/admin/articles/{row['id']}/edit">Modifier</a>
            <form method="post" action="/admin/articles/{row['id']}/delete"><button class="button small danger" type="submit">Supprimer</button></form>
          </td>
        </tr>
        """
        for row in rows
    )
    content = f"""
    <div class="admin-toolbar"><a class="button primary" href="/admin/articles/new">Nouvel article</a></div>
    <table class="admin-table">
      <thead><tr><th>Article</th><th>Publié</th><th>Accueil</th><th></th></tr></thead>
      <tbody>{table or '<tr><td colspan="4">Aucun article.</td></tr>'}</tbody>
    </table>
    """
    return admin_shell("Articles", content, "/admin/articles")


def admin_article_edit_page(article_id: int | None = None) -> str:
    row = None
    if article_id is not None:
        with connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        if row is None:
            return not_found_page()
    title = "Nouvel article" if row is None else "Modifier l’article"
    return admin_shell(title, article_form(row), "/admin/articles")


def admin_photos_page() -> str:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM photos ORDER BY created_at DESC").fetchall()
    items = "".join(
        f"""
        <figure class="photo-tile">
          <img src="/static/uploads/{e(row['filename'])}" alt="{e(row['title'] or 'Photo du jardin')}">
          <figcaption>
            <strong>{e(row['title'] or 'Photo du jardin')}</strong>
            <span>{e(row['caption'] or '')}</span>
            <em>{e(photo_visibility_label(row['visibility']))}</em>
            <form class="inline-photo-form" method="post" action="/admin/photos/{row['id']}/visibility">
              <select name="visibility">{photo_visibility_options(row['visibility'])}</select>
              <button class="button small secondary" type="submit">Changer</button>
            </form>
            <form method="post" action="/admin/photos/{row['id']}/delete"><button class="button small danger" type="submit">Supprimer</button></form>
          </figcaption>
        </figure>
        """
        for row in rows
    )
    content = f"""
    <form class="form-panel" method="post" action="/admin/photos/upload" enctype="multipart/form-data">
      <label>Image<input type="file" name="photo" accept="image/*" required></label>
      <label>Titre<input name="title"></label>
      <label>Légende<textarea name="caption" rows="4"></textarea></label>
      <label>Visibilité
        <select name="visibility">
          {photo_visibility_options("gallery", default="gallery")}
        </select>
      </label>
      <button class="button primary" type="submit">Ajouter la photo</button>
    </form>
    <div class="photo-grid admin-photo-grid">{items or empty_state("Aucune photo ajoutée.")}</div>
    """
    return admin_shell("Photos", content, "/admin/photos")


def admin_messages_page() -> str:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
    items = "".join(
        f"""
        <article class="message-card {'done' if row['handled'] else ''}">
          <header>
            <div>
              <strong>{e(row['name'])}</strong>
              <a href="mailto:{e(row['email'])}">{e(row['email'])}</a>
            </div>
            <span>{format_date(row['created_at'][:10])}</span>
          </header>
          <h3>{e(row['subject'] or 'Sans sujet')}</h3>
          {paragraphs(row['body'])}
          <form method="post" action="/admin/messages/{row['id']}/toggle">
            <button class="button small secondary" type="submit">{'Marquer à traiter' if row['handled'] else 'Marquer traité'}</button>
          </form>
        </article>
        """
        for row in rows
    )
    return admin_shell("Messages", f'<div class="list-stack">{items or empty_state("Aucun message.")}</div>', "/admin/messages")


def admin_users_page(current_user: sqlite3.Row) -> str:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM admin_users ORDER BY role DESC, username").fetchall()
    items = "".join(
        f"""
        <tr>
          <td><strong>{e(row['display_name'])}</strong><span>@{e(row['username'])}</span></td>
          <td>{e(role_label(row['role']))}</td>
          <td>{'Actif' if row['active'] else 'Désactivé'}</td>
          <td>
            <form class="table-form" method="post" action="/admin/users/{row['id']}/save">
              <input name="display_name" value="{e(row['display_name'])}" required>
              <select name="role">{role_options(row['role'])}</select>
              <label class="inline-check"><input type="checkbox" name="active" value="1" {'checked' if row['active'] else ''} {'disabled' if row['id'] == current_user['id'] else ''}> Actif</label>
              <button class="button small secondary" type="submit">Enregistrer</button>
            </form>
            <form class="table-form" method="post" action="/admin/users/{row['id']}/password">
              <input type="password" name="password" minlength="8" placeholder="Nouveau mot de passe">
              <button class="button small secondary" type="submit">Changer le mot de passe</button>
            </form>
          </td>
        </tr>
        """
        for row in rows
    )
    content = f"""
    <form class="form-panel" method="post" action="/admin/users/create">
      <div class="form-row">
        <label>Identifiant<input name="username" required minlength="3" maxlength="32" pattern="[A-Za-z0-9_.-]+"></label>
        <label>Nom affiché<input name="display_name" required></label>
      </div>
      <div class="form-row">
        <label>Rôle<select name="role">{role_options("admin")}</select></label>
        <label>Mot de passe<input type="password" name="password" required minlength="8" autocomplete="new-password"></label>
      </div>
      <button class="button primary" type="submit">Créer le compte</button>
    </form>
    <table class="admin-table users-table">
      <thead><tr><th>Compte</th><th>Rôle</th><th>Statut</th><th>Gestion</th></tr></thead>
      <tbody>{items or '<tr><td colspan="4">Aucun compte.</td></tr>'}</tbody>
    </table>
    """
    return admin_shell("Comptes administrateurs", content, "/admin/users")


def not_found_page() -> str:
    body = """
    <section class="page-hero compact-hero">
      <p class="eyebrow">404</p>
      <h1>Page introuvable</h1>
      <p>La page demandée n’existe pas ou a été déplacée.</p>
      <a class="button primary" href="/">Retour à l’accueil</a>
    </section>
    """
    return layout("Page introuvable", body, "/")


def session_value(user_id: int) -> str:
    issued_at = int(time.time())
    data = f"{user_id}:{issued_at}"
    signature = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}.{signature}"


def parse_session(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    try:
        data, signature = raw.rsplit(".", 1)
        user_id, issued_at = data.split(":", 1)
    except ValueError:
        return None
    expected = hmac.new(SESSION_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return None
    try:
        issued = int(issued_at)
        identifier = int(user_id)
    except ValueError:
        return None
    if time.time() - issued > SESSION_MAX_AGE_SECONDS:
        return None
    return identifier, issued


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, Upload]]:
    message = BytesParser(policy=email_policy).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    fields: dict[str, str] = {}
    files: dict[str, Upload] = {}
    if not message.is_multipart():
        return fields, files
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename:
            files[name] = Upload(filename, part.get_content_type(), payload)
        else:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, "replace")
    return fields, files


def safe_upload_name(original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Format d’image non accepté.")
    stem = slugify(Path(original_name).stem)[:48]
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}-{stem}{suffix}"


def save_photo_upload(
    conn: sqlite3.Connection,
    upload: Upload,
    title: str = "",
    caption: str = "",
    visibility: str = "both",
) -> str | None:
    if not upload or not upload.data or len(upload.data) > MAX_UPLOAD_BYTES:
        return None
    filename = safe_upload_name(upload.filename)
    (UPLOAD_DIR / filename).write_bytes(upload.data)
    conn.execute(
        "INSERT INTO photos (filename, title, caption, visibility, created_at) VALUES (?, ?, ?, ?, ?)",
        (filename, title, caption, normalize_photo_visibility(visibility), now_iso()),
    )
    return f"/static/uploads/{filename}"


def save_logo_upload(upload: Upload) -> str | None:
    if not upload or not upload.data or len(upload.data) > MAX_UPLOAD_BYTES:
        return None
    filename = safe_upload_name(f"logo-{upload.filename}")
    (UPLOAD_DIR / filename).write_bytes(upload.data)
    return f"/static/uploads/{filename}"


def save_cropped_article_image(
    conn: sqlite3.Connection,
    data_url: str,
    title: str,
    caption: str,
) -> str | None:
    if not data_url:
        return None
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,(.+)", data_url, re.DOTALL)
    if not match:
        return None
    image_type, encoded = match.groups()
    extension = "jpg" if image_type == "jpeg" else image_type
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not data or len(data) > MAX_UPLOAD_BYTES:
        return None
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}-{slugify(title)}-cover.{extension}"
    (UPLOAD_DIR / filename).write_bytes(data)
    conn.execute(
        "INSERT INTO photos (filename, title, caption, visibility, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            filename,
            f"Image de l’article : {title}",
            caption,
            "article",
            now_iso(),
        ),
    )
    return f"/static/uploads/{filename}"


def send_contact_email(form: dict[str, str]) -> bool:
    recipient = CONTACT_TO or read_settings().get("contact_email", "")
    if not SMTP_HOST or not recipient:
        return False

    message = EmailMessage()
    subject = form.get("subject", "").strip() or "Message depuis le site Vert-Tige"
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = recipient
    if form.get("email"):
        message["Reply-To"] = form["email"]
    message.set_content(
        f"Nom : {form.get('name', '')}\n"
        f"Email : {form.get('email', '')}\n"
        f"Sujet : {subject}\n\n"
        f"{form.get('body', '')}"
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except OSError:
        return False


class VertTigeHandler(BaseHTTPRequestHandler):
    server_version = "VertTige/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = self.clean_path(parsed.path)
        query = parse_qs(parsed.query)

        if path.startswith("/static/"):
            self.serve_static(path)
            return

        if path == "/":
            self.respond_html(home_page())
        elif path == "/agenda":
            self.respond_html(agenda_page(query))
        elif path == "/articles":
            self.respond_html(articles_page())
        elif path.startswith("/articles/"):
            self.respond_html(article_page(unquote(path.removeprefix("/articles/"))))
        elif path == "/galerie":
            self.respond_html(gallery_page())
        elif path == "/contact":
            self.respond_html(contact_page(sent=query.get("sent") == ["1"]))
        elif path == "/admin/login":
            self.respond_html(login_page(error=query.get("error") == ["1"]))
        elif path == "/admin/logout":
            self.clear_session()
        elif path.startswith("/admin"):
            user = self.current_user()
            if not user:
                self.redirect("/admin/login")
                return
            self.route_admin_get(path, user)
        else:
            self.respond_html(not_found_page(), status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = self.clean_path(parsed.path)
        if path == "/admin/login":
            self.handle_login()
            return
        if path == "/contact":
            self.handle_contact()
            return
        if path.startswith("/admin"):
            user = self.current_user()
            if not user:
                self.redirect("/admin/login")
                return
            self.route_admin_post(path, user)
            return
        self.respond_html(not_found_page(), status=404)

    def route_admin_get(self, path: str, user: sqlite3.Row) -> None:
        if path == "/admin":
            self.respond_html(admin_dashboard())
        elif path == "/admin/home":
            self.respond_html(admin_home_page())
        elif path == "/admin/events":
            self.respond_html(admin_events_page())
        elif path == "/admin/events/new":
            self.respond_html(admin_event_edit_page())
        elif match := re.fullmatch(r"/admin/events/(\d+)/edit", path):
            self.respond_html(admin_event_edit_page(int(match.group(1))))
        elif path == "/admin/articles":
            self.respond_html(admin_articles_page())
        elif path == "/admin/articles/new":
            self.respond_html(admin_article_edit_page())
        elif match := re.fullmatch(r"/admin/articles/(\d+)/edit", path):
            self.respond_html(admin_article_edit_page(int(match.group(1))))
        elif path == "/admin/photos":
            self.respond_html(admin_photos_page())
        elif path == "/admin/messages":
            self.respond_html(admin_messages_page())
        elif path == "/admin/users":
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.respond_html(admin_users_page(user))
        else:
            self.respond_html(not_found_page(), status=404)

    def route_admin_post(self, path: str, user: sqlite3.Row) -> None:
        if path == "/admin/home":
            self.save_home()
        elif path == "/admin/events/save":
            self.save_event()
        elif match := re.fullmatch(r"/admin/events/(\d+)/save", path):
            self.save_event(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/events/(\d+)/delete", path):
            self.delete_row("events", int(match.group(1)), "/admin/events")
        elif path == "/admin/articles/save":
            self.save_article()
        elif match := re.fullmatch(r"/admin/articles/(\d+)/save", path):
            self.save_article(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/articles/(\d+)/delete", path):
            self.delete_row("articles", int(match.group(1)), "/admin/articles")
        elif path == "/admin/photos/upload":
            self.upload_photo()
        elif match := re.fullmatch(r"/admin/photos/(\d+)/visibility", path):
            self.update_photo_visibility(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/photos/(\d+)/delete", path):
            self.delete_photo(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/messages/(\d+)/toggle", path):
            self.toggle_message(int(match.group(1)))
        elif path == "/admin/users/create":
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.create_admin_user()
        elif match := re.fullmatch(r"/admin/users/(\d+)/save", path):
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.save_admin_user(int(match.group(1)), user)
        elif match := re.fullmatch(r"/admin/users/(\d+)/password", path):
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.change_admin_password(int(match.group(1)))
        else:
            self.respond_html(not_found_page(), status=404)

    def read_form(self) -> tuple[dict[str, str], dict[str, Upload]]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if length > MAX_UPLOAD_BYTES and content_type.startswith("multipart/form-data"):
            return {}, {}
        if content_type.startswith("multipart/form-data"):
            return parse_multipart(content_type, body)
        parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items()}, {}

    def save_home(self) -> None:
        form, files = self.read_form()
        allowed = ["site_title", "tagline", "contact_email", "home_intro", "logo_url"]
        if form.get("contact_email") and not valid_email(form.get("contact_email", "").strip()):
            self.redirect("/admin/home")
            return
        current_logo = read_settings().get("logo_url", "")
        logo_url = "" if form.get("remove_logo") == "1" else current_logo
        logo_file = files.get("logo_file")
        if logo_file and logo_file.data:
            try:
                uploaded_logo = save_logo_upload(logo_file)
            except ValueError:
                uploaded_logo = None
            if uploaded_logo:
                logo_url = uploaded_logo
        with connect() as conn:
            for key in allowed:
                value = logo_url if key == "logo_url" else form.get(key, "").strip()
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
        self.redirect("/admin/home")

    def save_event(self, event_id: int | None = None) -> None:
        form, _ = self.read_form()
        title = form.get("title", "").strip()
        starts_on = form.get("starts_on", "").strip()
        ends_on = form.get("ends_on", "").strip()
        start_time = form.get("start_time", "").strip()
        end_time = form.get("end_time", "").strip()
        if (
            not title
            or not starts_on
            or not valid_iso_date(starts_on)
            or (ends_on and not valid_iso_date(ends_on))
            or not valid_time(start_time)
            or not valid_time(end_time)
        ):
            self.redirect("/admin/events")
            return
        if ends_on and date.fromisoformat(ends_on) < date.fromisoformat(starts_on):
            self.redirect("/admin/events")
            return
        values = (
            title,
            starts_on,
            ends_on,
            start_time,
            end_time,
            form.get("location", "").strip(),
            form.get("address", "").strip(),
            form.get("description", "").strip(),
        )
        with connect() as conn:
            if event_id is None:
                conn.execute(
                    """
                    INSERT INTO events
                        (title, starts_on, ends_on, start_time, end_time, location, address, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now_iso()),
                )
            else:
                conn.execute(
                    """
                    UPDATE events
                    SET title = ?, starts_on = ?, ends_on = ?, start_time = ?, end_time = ?,
                        location = ?, address = ?, description = ?
                    WHERE id = ?
                    """,
                    (*values, event_id),
                )
        self.redirect("/admin/events")

    def save_article(self, article_id: int | None = None) -> None:
        form, files = self.read_form()
        title = form.get("title", "").strip()
        if not title:
            self.redirect("/admin/articles")
            return
        with connect() as conn:
            slug = unique_slug(conn, title, article_id)
            image_url = form.get("current_image_url", "").strip() or "/static/hero-garden.png"
            image_choice = form.get("image_choice", "").strip()
            if image_choice:
                image_url = image_choice
            cropped_image_data = form.get("cropped_image_data", "").strip()
            cropped_saved = False
            if cropped_image_data:
                cropped_url = save_cropped_article_image(
                    conn,
                    cropped_image_data,
                    title,
                    form.get("summary", "").strip(),
                )
                if cropped_url:
                    image_url = cropped_url
                    cropped_saved = True
            upload = files.get("article_image")
            if not cropped_saved and upload and upload.data:
                try:
                    uploaded_url = save_photo_upload(
                        conn,
                        upload,
                        title=f"Image de l’article : {title}",
                        caption=form.get("summary", "").strip(),
                        visibility="article",
                    )
                except ValueError:
                    uploaded_url = None
                if uploaded_url:
                    image_url = uploaded_url
            values = (
                title,
                slug,
                form.get("summary", "").strip(),
                form.get("body", "").strip(),
                image_url,
                1 if form.get("featured") == "1" else 0,
                1 if form.get("published") == "1" else 0,
                now_iso(),
            )
            if article_id is None:
                conn.execute(
                    """
                    INSERT INTO articles
                        (title, slug, summary, body, image_url, featured, published, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now_iso()),
                )
            else:
                conn.execute(
                    """
                    UPDATE articles
                    SET title = ?, slug = ?, summary = ?, body = ?, image_url = ?,
                        featured = ?, published = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (*values, article_id),
                )
        self.redirect("/admin/articles")

    def upload_photo(self) -> None:
        form, files = self.read_form()
        upload = files.get("photo")
        if upload and upload.data:
            try:
                with connect() as conn:
                    save_photo_upload(
                        conn,
                        upload,
                        form.get("title", "").strip(),
                        form.get("caption", "").strip(),
                        normalize_photo_visibility(form.get("visibility"), default="gallery"),
                    )
            except ValueError:
                self.redirect("/admin/photos")
                return
        self.redirect("/admin/photos")

    def update_photo_visibility(self, photo_id: int) -> None:
        form, _ = self.read_form()
        visibility = normalize_photo_visibility(form.get("visibility"))
        with connect() as conn:
            conn.execute(
                "UPDATE photos SET visibility = ? WHERE id = ?",
                (visibility, photo_id),
            )
        self.redirect("/admin/photos")

    def handle_contact(self) -> None:
        form, _ = self.read_form()
        name = form.get("name", "").strip()
        email = form.get("email", "").strip()
        body = form.get("body", "").strip()
        if not (name and email and body and valid_email(email)):
            self.redirect("/contact")
            return
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (name, email, subject, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    form.get("subject", "").strip(),
                    body,
                    now_iso(),
                ),
            )
        send_contact_email(form)
        self.redirect("/contact?sent=1")

    def handle_login(self) -> None:
        form, _ = self.read_form()
        username = normalize_username(form.get("username"))
        password = form.get("password", "")
        with connect() as conn:
            user = conn.execute(
                "SELECT * FROM admin_users WHERE username = ? AND active = 1",
                (username,),
            ).fetchone()
        if user and verify_password(user, password):
            body = b""
            self.send_response(303)
            self.send_header("Location", "/admin")
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={session_value(user['id'])}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_MAX_AGE_SECONDS}",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.redirect("/admin/login?error=1")

    def clear_session(self) -> None:
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
        )
        self.end_headers()

    def delete_row(self, table: str, row_id: int, redirect_to: str) -> None:
        if table not in {"events", "articles"}:
            self.redirect(redirect_to)
            return
        with connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        self.redirect(redirect_to)

    def delete_photo(self, photo_id: int) -> None:
        with connect() as conn:
            row = conn.execute("SELECT filename FROM photos WHERE id = ?", (photo_id,)).fetchone()
            if row:
                conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
                conn.execute(
                    "UPDATE articles SET image_url = ? WHERE image_url = ?",
                    ("/static/hero-garden.png", f"/static/uploads/{row['filename']}"),
                )
                path = UPLOAD_DIR / row["filename"]
                if path.exists() and path.is_file():
                    path.unlink()
        self.redirect("/admin/photos")

    def toggle_message(self, message_id: int) -> None:
        with connect() as conn:
            conn.execute(
                "UPDATE messages SET handled = CASE handled WHEN 1 THEN 0 ELSE 1 END WHERE id = ?",
                (message_id,),
            )
        self.redirect("/admin/messages")

    def create_admin_user(self) -> None:
        form, _ = self.read_form()
        username = normalize_username(form.get("username"))
        display_name = form.get("display_name", "").strip() or username
        password = form.get("password", "")
        role = normalize_role(form.get("role"))
        if len(username) < 3 or len(password) < 8:
            self.redirect("/admin/users")
            return
        salt, password_hash = hash_password(password)
        created = now_iso()
        try:
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO admin_users
                        (username, display_name, role, password_salt, password_hash, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (username, display_name, role, salt, password_hash, 1, created, created),
                )
        except sqlite3.IntegrityError:
            pass
        self.redirect("/admin/users")

    def save_admin_user(self, user_id: int, current_user: sqlite3.Row) -> None:
        form, _ = self.read_form()
        display_name = form.get("display_name", "").strip()
        role = normalize_role(form.get("role"))
        active = 1 if form.get("active") == "1" else 0
        if user_id == current_user["id"]:
            role = "owner"
            active = 1
        if not display_name:
            self.redirect("/admin/users")
            return
        with connect() as conn:
            conn.execute(
                "UPDATE admin_users SET display_name = ?, role = ?, active = ?, updated_at = ? WHERE id = ?",
                (display_name, role, active, now_iso(), user_id),
            )
        self.redirect("/admin/users")

    def change_admin_password(self, user_id: int) -> None:
        form, _ = self.read_form()
        password = form.get("password", "")
        if len(password) < 8:
            self.redirect("/admin/users")
            return
        salt, password_hash = hash_password(password)
        with connect() as conn:
            conn.execute(
                """
                UPDATE admin_users
                SET password_salt = ?, password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (salt, password_hash, now_iso(), user_id),
            )
        self.redirect("/admin/users")

    def current_user(self) -> sqlite3.Row | None:
        raw_cookie = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(raw_cookie)
        morsel = jar.get(SESSION_COOKIE)
        parsed = parse_session(morsel.value if morsel else None)
        if not parsed:
            return None
        user_id, _issued = parsed
        with connect() as conn:
            return conn.execute(
                "SELECT * FROM admin_users WHERE id = ? AND active = 1",
                (user_id,),
            ).fetchone()

    def is_authenticated(self) -> bool:
        return self.current_user() is not None

    def serve_static(self, path: str) -> None:
        relative = Path(unquote(path.removeprefix("/static/")))
        target = (STATIC_DIR / relative).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self.respond_html(not_found_page(), status=404)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def respond_html(self, content: str, status: int = 200) -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    @staticmethod
    def clean_path(path: str) -> str:
        if path != "/" and path.endswith("/"):
            return path.rstrip("/")
        return path

    def log_message(self, format: str, *args: object) -> None:
        write_log(f"{self.address_string()} {format % args}")


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), VertTigeHandler)
    write_log(f"Vert-Tige est prêt : http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        write_log("Arrêt du serveur.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
