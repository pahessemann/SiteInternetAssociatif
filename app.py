from __future__ import annotations

import calendar
import base64
import binascii
import hashlib
import hmac
import html
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.parser import BytesParser
from email.policy import default as email_policy
from html.parser import HTMLParser
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
CSP_NONCE_PLACEHOLDER = "__VERT_TIGE_CSP_NONCE__"

HOST = os.getenv("VERT_TIGE_HOST", "127.0.0.1")
PORT = int(os.getenv("VERT_TIGE_PORT", "8000"))
PUBLIC_URL = os.getenv("VERT_TIGE_PUBLIC_URL", "").strip().rstrip("/")
ADMIN_PASSWORD = os.getenv("VERT_TIGE_ADMIN_PASSWORD", "jardin")
SESSION_SECRET = os.getenv("VERT_TIGE_SECRET", "change-this-secret-before-production")
SESSION_COOKIE = "vert_tige_session"
SESSION_MAX_AGE_SECONDS = int(os.getenv("VERT_TIGE_SESSION_SECONDS", str(12 * 60 * 60)))
PASSWORD_ITERATIONS = 390_000
ROLE_LABELS = {
    "owner": "Référent",
    "admin": "Administrateur",
}

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

OLD_HOME_INTRO = (
    "Vert-Tige est un jardin partagé du 14e arrondissement : un lieu pour "
    "cultiver, transmettre, bricoler, composter et créer des rencontres de quartier."
)
NEW_HOME_INTRO = "Échanger, apprendre, transmettre, animer, protéger"
HOME_DESCRIPTION_SIZES = {
    "small": "Petite",
    "normal": "Normale",
    "large": "Grande",
    "xlarge": "Très grande",
}
RICH_TEXT_SIZE_CLASSES = {f"text-size-{size}" for size in HOME_DESCRIPTION_SIZES}

DEFAULT_SETTINGS = {
    "site_title": "Vert-Tige",
    "tagline": "Jardin partagé à Paris 14",
    "home_intro": NEW_HOME_INTRO,
    "home_about_text": OLD_HOME_INTRO,
    "home_image_url": "/static/hero-garden.png",
    "home_hero_eyebrow": "Jardin partagé · Paris 14",
    "home_primary_button_label": "Voir l’agenda",
    "home_secondary_button_label": "Contacter l’association",
    "home_about_eyebrow": "Association de quartier",
    "home_about_title": "Un site pour faire vivre le jardin entre deux permanences",
    "home_events_eyebrow": "Prochains rendez-vous",
    "home_events_title": "Agenda du jardin",
    "home_events_link_label": "Tout voir",
    "home_events_empty": "Aucun rendez-vous à venir pour le moment.",
    "home_articles_eyebrow": "Carnet de bord",
    "home_articles_title": "Articles mis en avant",
    "home_articles_link_label": "Tous les articles",
    "home_articles_empty": "Les articles mis en avant apparaîtront ici.",
    "home_photos_eyebrow": "Banque de photos",
    "home_photos_title": "Images du jardin",
    "home_photos_link_label": "Ouvrir la galerie",
    "home_photos_empty_title": "La galerie est prête",
    "home_photos_empty_text": "Les premières photos ajoutées depuis l’administration apparaîtront ici.",
    "contact_email": "contact@vert-tige.local",
    "logo_url": "",
    "facebook_url": "",
    "instagram_url": "",
    "footer_address": "37, rue de Coulmiers – 75014 Paris",
    "footer_copyright": "Copyright ©2026 Jardin Vert-Tige",
    "instagram_banner_text": "RETROUVEZ LE JARDIN VERT-TIGE SUR INSTAGRAM",
    "instagram_banner_image_url": "/static/hero-garden.png",
    "practical_eyebrow": "Infos pratiques",
    "practical_title": "Venir au jardin Vert-Tige",
    "practical_intro": "Adresse, transports et horaires utiles pour rejoindre le jardin partagé.",
    "practical_address": "37 rue de Coulmiers, 75014 Paris",
    "practical_map_embed_url": (
        "https://www.openstreetmap.org/export/embed.html?"
        "bbox=2.3197%2C48.8224%2C2.3318%2C48.8296&layer=mapnik&marker=48.8260%2C2.3256"
    ),
    "practical_map_link_url": "https://www.openstreetmap.org/search?query=37%20rue%20de%20Coulmiers%2075014%20Paris",
    "practical_bus": "Bus 38, 92 : Porte d’Orléans",
    "practical_metro": "Métro : Ligne 4, Porte d’Orléans ou Alésia",
    "practical_tram": "Tram : T3a, Jean Moulin ou Porte d’Orléans",
    "practical_velib": "Station Vélib : rue Auguste Cain",
    "practical_opening": "Jours fériés, samedis et dimanches : de 15 h à 18 h, selon les disponibilités des bénévoles.",
    "legal_publisher": "Association Vert-Tige",
    "legal_responsible": "",
    "legal_hosting": "",
    "legal_text": "",
    "terms_text": "",
    "google_ads_id": "",
    "google_ads_conversion_label": "",
    "analytics_provider": "",
    "analytics_site_id": "",
    "site_url": "",
    "seo_description": (
        "Vert-Tige est un jardin partagé associatif du 14e arrondissement de Paris, "
        "avec des ateliers, des événements, des articles et une galerie photo."
    ),
    "seo_image_url": "/static/hero-garden.png",
    "google_site_verification": "",
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


def rich_text_has_markup(value: str | None) -> bool:
    return bool(re.search(r"</?(p|div|br|strong|b|em|i|u|span)\b", value or "", re.IGNORECASE))


class RichTextSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"p", "div"}:
            self.parts.append("<p>")
            self.open_tags.append("p")
        elif tag == "br":
            self.parts.append("<br>")
        elif tag in {"strong", "b"}:
            self.parts.append("<strong>")
            self.open_tags.append("strong")
        elif tag in {"em", "i"}:
            self.parts.append("<em>")
            self.open_tags.append("em")
        elif tag == "u":
            self.parts.append("<u>")
            self.open_tags.append("u")
        elif tag == "span":
            class_value = " ".join(value or "" for name, value in attrs if name.lower() == "class")
            class_name = next((item for item in class_value.split() if item in RICH_TEXT_SIZE_CLASSES), "")
            if class_name:
                self.parts.append(f'<span class="{e(class_name)}">')
                self.open_tags.append("span")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        output_tag = {
            "div": "p",
            "p": "p",
            "b": "strong",
            "strong": "strong",
            "i": "em",
            "em": "em",
            "u": "u",
            "span": "span",
        }.get(tag)
        if not output_tag or output_tag not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.parts.append(f"</{current}>")
            if current == output_tag:
                break

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.parts.append(e(data))

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        cleaned = "".join(self.parts)
        cleaned = re.sub(r"<p>(?:\s|<br>)*</p>", "", cleaned)
        return cleaned.strip()


def sanitize_rich_text(value: str | None) -> str:
    parser = RichTextSanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.get_html()


def render_home_description(value: str | None) -> str:
    if rich_text_has_markup(value):
        return sanitize_rich_text(value)
    return paragraphs(value)


def editor_home_description(value: str | None) -> str:
    content = render_home_description(value)
    return content or "<p><br></p>"


def rich_text_size_options() -> str:
    options = ['<option value="">Taille...</option>']
    options.extend(
        f'<option value="{e(size)}">{e(label)}</option>'
        for size, label in HOME_DESCRIPTION_SIZES.items()
    )
    return "".join(options)


def text_content(value: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]*>", " ", value or ""))


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


def valid_optional_url(value: str) -> bool:
    if not value:
        return True
    return bool(re.fullmatch(r"https://[^\s]+", value))


def setting_enabled(settings: dict[str, str], key: str, default: bool = True) -> bool:
    value = settings.get(key)
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return False
    return text not in {"0", "false", "non", "no", "off"}


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


def int_or_none(value: str | None) -> int | None:
    try:
        return int(value or "")
    except ValueError:
        return None


def unique_album_slug(conn: sqlite3.Connection, name: str) -> str:
    base = slugify(name)
    candidate = base
    index = 2
    while conn.execute("SELECT id FROM photo_albums WHERE slug = ?", (candidate,)).fetchone():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def album_options(rows: list[sqlite3.Row], selected_id: int | None = None) -> str:
    return "".join(
        f'<option value="{row["id"]}" {"selected" if row["id"] == selected_id else ""}>{e(row["name"])}</option>'
        for row in rows
    )


def photo_library_options(rows: list[sqlite3.Row], selected_url: str = "") -> str:
    options = []
    for row in rows:
        image_url = f"/static/uploads/{row['filename']}"
        selected = "selected" if selected_url == image_url else ""
        album = f" · {row['album_name']}" if row["album_name"] else ""
        label = f"{row['title'] or row['filename']}{album} · {photo_visibility_label(row['visibility'])}"
        options.append(f'<option value="{e(image_url)}" {selected}>{e(label)}</option>')
    return "".join(options)


def existing_photo_upload_url(value: str | None) -> str:
    image_url = (value or "").strip()
    prefix = "/static/uploads/"
    if not image_url.startswith(prefix):
        return ""
    filename = image_url.removeprefix(prefix)
    if not filename or "/" in filename or "\\" in filename:
        return ""
    with connect() as conn:
        row = conn.execute("SELECT id FROM photos WHERE filename = ?", (filename,)).fetchone()
    return image_url if row else ""


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


def messaging_settings_form(settings: dict[str, str]) -> str:
    return f"""
    <form class="form-panel messaging-form" method="post" action="/admin/messages/settings">
      <h2>Configuration de la messagerie</h2>
      <div class="settings-section">
        <h2>Formulaire de contact</h2>
        <label>Email affiché sur le site<input type="email" name="contact_email" value="{e(settings.get('contact_email', ''))}"></label>
        <p class="form-note">Les messages restent conservés dans l’administration. Après envoi du formulaire, le visiteur peut ouvrir son application mail avec un brouillon prérempli.</p>
      </div>
      <button class="button primary" type="submit">Enregistrer la messagerie</button>
    </form>
    """


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


def versioned_static_url(path: str) -> str:
    target = (BASE_DIR / path.lstrip("/")).resolve()
    try:
        version = int(target.stat().st_mtime)
    except OSError:
        version = 1
    return f"{path}?v={version}"


def compact_text(value: str | None, fallback: str = "", limit: int = 170) -> str:
    text = re.sub(r"\s+", " ", text_content(value)).strip()
    if not text:
        text = re.sub(r"\s+", " ", text_content(fallback)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


SEARCH_STOP_WORDS = {
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "chez",
    "dans",
    "des",
    "du",
    "elle",
    "elles",
    "en",
    "est",
    "et",
    "la",
    "le",
    "les",
    "leur",
    "leurs",
    "nos",
    "notre",
    "par",
    "pas",
    "plus",
    "pour",
    "que",
    "qui",
    "sur",
    "un",
    "une",
    "vos",
    "votre",
}


def normalize_search_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def search_tokens(value: str | None) -> list[str]:
    return [
        token
        for token in normalize_search_text(value).split()
        if len(token) > 1 and token not in SEARCH_STOP_WORDS
    ]


def article_search_score(row: sqlite3.Row, tokens: list[str], phrase: str) -> int:
    title = normalize_search_text(row["title"])
    summary = normalize_search_text(row["summary"])
    body = normalize_search_text(row["body"])
    score = 0
    for token in tokens:
        token_score = 0
        if token in title:
            token_score += 45
            if title.startswith(token):
                token_score += 10
        if token in summary:
            token_score += 24
        if token in body:
            token_score += 9
        if token_score == 0:
            return 0
        score += token_score
    if phrase and len(phrase) > 2:
        if phrase in title:
            score += 90
        elif phrase in summary:
            score += 45
        elif phrase in body:
            score += 20
    return score


def filter_article_rows(rows: list[sqlite3.Row], query: str) -> list[sqlite3.Row]:
    tokens = search_tokens(query)
    if not query.strip():
        return rows
    if not tokens:
        return []
    phrase = normalize_search_text(query)
    scored = [
        (article_search_score(row, tokens, phrase), row["created_at"], row)
        for row in rows
    ]
    matches = [item for item in scored if item[0] > 0]
    matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in matches]


def contact_mailto_url(settings: dict[str, str], message: sqlite3.Row | None) -> str:
    recipient = (settings.get("contact_email") or "").strip()
    if not message or not valid_email(recipient):
        return ""
    subject = (message["subject"] or "Message depuis le site Vert-Tige").strip()
    body = (
        "Bonjour,\n\n"
        f"{message['body']}\n\n"
        "--\n"
        f"{message['name']}\n"
        f"{message['email']}\n"
    )
    return (
        f"mailto:{quote(recipient, safe='@.+-_')}"
        f"?subject={quote(subject, safe='')}"
        f"&body={quote(body, safe='')}"
    )


def contact_message_by_token(token: str) -> sqlite3.Row | None:
    if not re.fullmatch(r"[a-f0-9]{32}", token or ""):
        return None
    with connect() as conn:
        return conn.execute("SELECT * FROM messages WHERE mail_token = ?", (token,)).fetchone()


def public_base_url(settings: dict[str, str]) -> str:
    if PUBLIC_URL:
        return PUBLIC_URL
    configured = (settings.get("site_url") or "").strip().rstrip("/")
    if configured:
        return configured
    return f"http://{HOST}:{PORT}"


def session_cookie_header(value: str, max_age: int) -> str:
    secure = "; Secure" if PUBLIC_URL.startswith("https://") else ""
    return f"{SESSION_COOKIE}={value}; Path=/; HttpOnly; SameSite=Lax{secure}; Max-Age={max_age}"


def absolute_url(path_or_url: str | None, settings: dict[str, str]) -> str:
    value = (path_or_url or "").strip()
    if not value:
        value = "/"
    if re.fullmatch(r"https?://[^\s]+", value):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return public_base_url(settings) + value


def page_title(title: str, settings: dict[str, str]) -> str:
    site_title = settings["site_title"]
    if title == "Accueil":
        return f"{site_title} · {settings['tagline']}"
    return f"{title} · {site_title}"


def json_ld_script(data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json" nonce="{CSP_NONCE_PLACEHOLDER}">{payload}</script>'


def organization_schema(settings: dict[str, str]) -> dict[str, object]:
    schema: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings["site_title"],
        "url": public_base_url(settings),
        "description": compact_text(settings.get("seo_description"), settings.get("home_intro")),
    }
    if settings.get("contact_email"):
        schema["email"] = settings["contact_email"]
    if settings.get("practical_address"):
        schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": "37 rue de Coulmiers",
            "postalCode": "75014",
            "addressLocality": "Paris",
            "addressCountry": "FR",
        }
    logo = settings.get("logo_url") or settings.get("seo_image_url")
    if logo:
        schema["logo"] = absolute_url(logo, settings)
    same_as = [
        url
        for url in [settings.get("facebook_url", ""), settings.get("instagram_url", "")]
        if url
    ]
    if same_as:
        schema["sameAs"] = same_as
    return schema


def website_schema(settings: dict[str, str]) -> dict[str, object]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings["site_title"],
        "url": public_base_url(settings),
        "description": compact_text(settings.get("seo_description"), settings.get("home_intro")),
        "potentialAction": {
            "@type": "SearchAction",
            "target": absolute_url("/articles?q={search_term_string}", settings),
            "query-input": "required name=search_term_string",
        },
    }


def event_schema(row: sqlite3.Row, settings: dict[str, str]) -> dict[str, object]:
    start = row["starts_on"]
    if row["start_time"]:
        start = f"{start}T{row['start_time']}:00"
    end = row["ends_on"] or row["starts_on"]
    if row["end_time"]:
        end = f"{end}T{row['end_time']}:00"
    schema: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": row["title"],
        "startDate": start,
        "endDate": end,
        "description": compact_text(row["description"], row["title"]),
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "eventStatus": "https://schema.org/EventScheduled",
        "organizer": {
            "@type": "Organization",
            "name": settings["site_title"],
            "url": public_base_url(settings),
        },
        "location": {
            "@type": "Place",
            "name": row["location"] or "Jardin Vert-Tige",
            "address": row["address"] or "Paris 14",
        },
    }
    return schema


def article_schema(row: sqlite3.Row, settings: dict[str, str]) -> dict[str, object]:
    image = row["image_url"] or settings.get("seo_image_url")
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": row["title"],
        "description": compact_text(row["summary"], row["body"]),
        "image": absolute_url(image, settings),
        "datePublished": row["created_at"],
        "dateModified": row["updated_at"],
        "url": absolute_url(f"/articles/{quote(row['slug'])}", settings),
        "author": {
            "@type": "Organization",
            "name": settings["site_title"],
        },
        "publisher": organization_schema(settings),
    }


def seo_head(
    settings: dict[str, str],
    title: str,
    current_path: str,
    description: str | None = None,
    image_url: str | None = None,
    og_type: str = "website",
    structured_data: list[dict[str, object]] | None = None,
    indexable: bool = True,
) -> str:
    title_text = page_title(title, settings)
    description_text = compact_text(
        description,
        settings.get("seo_description") or settings.get("home_intro") or settings.get("tagline"),
    )
    image = image_url or settings.get("seo_image_url") or "/static/hero-garden.png"
    canonical = absolute_url(current_path, settings)
    robots = "" if indexable else '<meta name="robots" content="noindex, nofollow">'
    verification = settings.get("google_site_verification", "").strip()
    verification_meta = (
        f'<meta name="google-site-verification" content="{e(verification)}">'
        if verification
        else ""
    )
    schemas = []
    if indexable:
        schemas.extend([organization_schema(settings), *(structured_data or [])])
        if current_path == "/":
            schemas.append(website_schema(settings))
    schema_html = "\n  ".join(json_ld_script(schema) for schema in schemas)
    return f"""
  <meta name="description" content="{e(description_text)}">
  {robots}
  {verification_meta}
  <link rel="canonical" href="{e(canonical)}">
  <meta property="og:site_name" content="{e(settings['site_title'])}">
  <meta property="og:title" content="{e(title_text)}">
  <meta property="og:description" content="{e(description_text)}">
  <meta property="og:type" content="{e(og_type)}">
  <meta property="og:url" content="{e(canonical)}">
  <meta property="og:image" content="{e(absolute_url(image, settings))}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(title_text)}">
  <meta name="twitter:description" content="{e(description_text)}">
  <meta name="twitter:image" content="{e(absolute_url(image, settings))}">
  {schema_html}"""


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
                album_id INTEGER,
                filename TEXT NOT NULL,
                title TEXT,
                caption TEXT,
                visibility TEXT NOT NULL DEFAULT 'both',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS photo_albums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                body TEXT NOT NULL,
                mail_token TEXT,
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
                "album_id": "INTEGER",
                "visibility": "TEXT NOT NULL DEFAULT 'both'",
            },
        )
        ensure_columns(
            conn,
            "messages",
            {
                "mail_token": "TEXT",
            },
        )
        conn.execute(
            "UPDATE photos SET visibility = 'both' WHERE visibility IS NULL OR visibility = ''"
        )
        album_count = conn.execute("SELECT COUNT(*) AS count FROM photo_albums").fetchone()["count"]
        if album_count == 0:
            conn.execute(
                "INSERT INTO photo_albums (name, slug, description, created_at) VALUES (?, ?, ?, ?)",
                ("Général", "general", "Photos non classées ou communes.", now_iso()),
            )
        default_album = conn.execute(
            "SELECT id FROM photo_albums ORDER BY id LIMIT 1"
        ).fetchone()
        if default_album:
            conn.execute(
                "UPDATE photos SET album_id = ? WHERE album_id IS NULL",
                (default_album["id"],),
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
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'home_intro' AND value = ?",
            (NEW_HOME_INTRO, OLD_HOME_INTRO),
        )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'footer_address' AND value = ?",
            ("37, rue de Coulmiers – 75014 Paris", "37, rue de Coulmiers – 75104 Paris"),
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


def social_icon_link(url: str, label: str, path: str, service: str) -> str:
    classes = f"social-link social-{service}"
    if not url:
        return f"""
    <span class="{classes} is-disabled" aria-label="{e(label)} non configuré" title="{e(label)} non configuré">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="{path}"></path></svg>
    </span>
    """
    return f"""
    <a class="{classes}" href="{e(url)}" target="_blank" rel="noopener noreferrer" aria-label="{e(label)}">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="{path}"></path></svg>
    </a>
    """


def instagram_footer_banner(settings: dict[str, str]) -> str:
    instagram_url = settings.get("instagram_url", "").strip()
    image_url = settings.get("instagram_banner_image_url") or settings.get("home_image_url") or "/static/hero-garden.png"
    text = settings.get("instagram_banner_text") or "RETROUVEZ LE JARDIN VERT-TIGE SUR INSTAGRAM"
    content = f"""
      <div class="instagram-banner-copy">
        <small>Instagram</small>
        <strong>{e(text)}</strong>
      </div>
      <figure class="instagram-banner-photo">
        <img src="{e(image_url)}" alt="">
      </figure>
    """
    if instagram_url:
        frame = f"""
    <a class="instagram-banner-frame" href="{e(instagram_url)}" target="_blank" rel="noopener noreferrer" aria-label="Retrouvez le jardin Vert-Tige sur Instagram">
      {content}
    </a>
        """
    else:
        frame = f"""
    <div class="instagram-banner-frame" aria-label="Instagram Vert-Tige">
      {content}
    </div>
        """
    return f"""
  <section class="instagram-footer-banner" aria-label="Instagram Vert-Tige">
    {frame}
  </section>
    """


def google_ads_head(settings: dict[str, str], track_conversion: bool) -> str:
    ads_id = settings.get("google_ads_id", "").strip()
    conversion_label = settings.get("google_ads_conversion_label", "").strip()
    analytics_provider = settings.get("analytics_provider", "").strip()
    analytics_site_id = settings.get("analytics_site_id", "").strip()
    analytics_meta = (
        f"""
  <meta name="analytics-provider" content="{e(analytics_provider)}">
  <meta name="analytics-site-id" content="{e(analytics_site_id)}">"""
        if analytics_provider and analytics_site_id
        else ""
    )
    if not ads_id:
        return analytics_meta
    conversion_meta = (
        '<meta name="google-ads-conversion" content="contact">'
        if track_conversion and conversion_label
        else ""
    )
    return f"""
  <meta name="google-ads-id" content="{e(ads_id)}">
  <meta name="google-ads-conversion-label" content="{e(conversion_label)}">
  {conversion_meta}
  {analytics_meta}"""


def cookie_consent_html() -> str:
    return """
  <div class="cookie-banner" data-cookie-banner hidden>
    <div>
      <strong>Gestion des cookies</strong>
      <p>Le site utilise uniquement les éléments nécessaires par défaut. Les statistiques, la publicité et les contenus externes ne sont activés qu’avec ton accord.</p>
    </div>
    <div class="cookie-actions">
      <button class="button secondary" type="button" data-cookie-refuse>Tout refuser</button>
      <button class="button primary" type="button" data-cookie-accept>Tout accepter</button>
    </div>
  </div>
    """


def layout(
    title: str,
    body: str,
    current_path: str = "/",
    track_conversion: bool = False,
    description: str | None = None,
    image_url: str | None = None,
    og_type: str = "website",
    structured_data: list[dict[str, object]] | None = None,
    indexable: bool = True,
) -> str:
    settings = read_settings()
    site_title = settings["site_title"]
    logo_url = settings.get("logo_url", "")
    stylesheet_url = versioned_static_url("/static/styles.css")
    editor_url = versioned_static_url("/static/article-editor.js")
    privacy_url = versioned_static_url("/static/privacy.js")
    favicon_url = settings.get("logo_url") or "/static/favicon.svg"
    facebook_path = "M22 12.06C22 6.49 17.52 2 11.94 2S2 6.49 2 12.06c0 5.02 3.66 9.19 8.44 9.94v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.9 3.77-3.9 1.09 0 2.23.2 2.23.2v2.46h-1.25c-1.24 0-1.63.77-1.63 1.56v1.89h2.78l-.44 2.91h-2.34V22c4.78-.75 8.44-4.92 8.44-9.94z"
    instagram_path = "M7.7 2h8.6A5.7 5.7 0 0 1 22 7.7v8.6a5.7 5.7 0 0 1-5.7 5.7H7.7A5.7 5.7 0 0 1 2 16.3V7.7A5.7 5.7 0 0 1 7.7 2zm0 2A3.7 3.7 0 0 0 4 7.7v8.6A3.7 3.7 0 0 0 7.7 20h8.6a3.7 3.7 0 0 0 3.7-3.7V7.7A3.7 3.7 0 0 0 16.3 4H7.7zm4.3 3.35A4.65 4.65 0 1 1 7.35 12 4.65 4.65 0 0 1 12 7.35zm0 2A2.65 2.65 0 1 0 14.65 12 2.65 2.65 0 0 0 12 9.35zm5.03-2.2a1.08 1.08 0 1 1-1.08 1.08 1.08 1.08 0 0 1 1.08-1.08z"
    gear_path = "M19.43 12.98c.04-.32.07-.65.07-.98s-.02-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1a7.28 7.28 0 0 0-1.69-.98L14.5 2.42A.5.5 0 0 0 14 2h-4a.5.5 0 0 0-.5.42L9.12 5.07c-.6.24-1.16.56-1.69.98l-2.49-1a.5.5 0 0 0-.61.22l-2 3.46c-.12.22-.07.49.12.64l2.11 1.65c-.04.32-.06.65-.06.98s.02.66.06.98l-2.11 1.65a.5.5 0 0 0-.12.64l2 3.46c.13.22.39.31.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.38-2.65c.6-.25 1.17-.58 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46a.5.5 0 0 0-.12-.64l-2.12-1.65zM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5z"
    social_links = (
        social_icon_link(settings.get("facebook_url", ""), "Facebook", facebook_path, "facebook")
        + social_icon_link(settings.get("instagram_url", ""), "Instagram", instagram_path, "instagram")
    )
    show_instagram_banner = current_path == "/" or current_path.startswith("/galerie")
    instagram_banner = instagram_footer_banner(settings) if show_instagram_banner else ""
    cookie_controls = "" if current_path.startswith("/admin") else cookie_consent_html()
    cookie_footer_button = (
        ""
        if current_path.startswith("/admin")
        else '<button class="footer-cookie-link" type="button" data-cookie-open>Gestion des cookies</button>'
    )
    tracking_head = "" if current_path.startswith("/admin") else google_ads_head(settings, track_conversion)
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
            nav_link("/infos-pratiques", "Infos pratiques", current_path),
            nav_link("/contact", "Contact", current_path),
        ]
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(page_title(title, settings))}</title>
  {seo_head(settings, title, current_path, description, image_url, og_type, structured_data, indexable)}
  <link rel="icon" href="{e(favicon_url)}">
  <link rel="stylesheet" href="{e(stylesheet_url)}">
  <script src="{e(editor_url)}" defer></script>
  <script src="{e(privacy_url)}" defer></script>
  {tracking_head}
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
  {instagram_banner}
  <footer class="site-footer">
    <div class="footer-address">
      <strong>{e(settings.get("footer_address") or "37, rue de Coulmiers – 75104 Paris")}</strong>
    </div>
    <div class="footer-center">
      <div class="footer-social">{social_links}</div>
      <span>{e(settings.get("footer_copyright") or "Copyright ©2026 Jardin Vert-Tige")}</span>
    </div>
    <div class="footer-links">
      <a href="/mentions-legales">Mentions légales</a>
      <a href="/conditions-generales-utilisation">Conditions générales d’utilisation</a>
      {cookie_footer_button}
      <a class="footer-admin-link" href="/admin" aria-label="Paramètres du site" title="Paramètres du site">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="{gear_path}"></path></svg>
      </a>
    </div>
  </footer>
  {cookie_controls}
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

    home_image = settings.get("home_image_url") or "/static/hero-garden.png"
    event_html = "".join(event_card(row) for row in events) or empty_state(settings["home_events_empty"])
    article_html = "".join(article_card(row) for row in articles) or empty_state(settings["home_articles_empty"])
    photo_html = render_photo_strip(photos, settings)
    about_text = settings.get("home_about_text") or settings["home_intro"]
    about_html = render_home_description(about_text)

    body = f"""
    <section class="hero">
      <img class="hero-bg" src="{e(home_image)}" alt="">
      <div class="hero-content">
        <p class="eyebrow">{e(settings["home_hero_eyebrow"])}</p>
        <h1>{e(settings["site_title"])}</h1>
        <p>{e(settings["home_intro"])}</p>
        <div class="button-row">
          <a class="button primary" href="/agenda">{e(settings["home_primary_button_label"])}</a>
          <a class="button secondary" href="/contact">{e(settings["home_secondary_button_label"])}</a>
        </div>
        <form class="home-article-search" method="get" action="/articles" role="search" aria-label="Rechercher dans les articles">
          <label for="home-article-search">Rechercher dans les articles</label>
          <div class="search-row">
            <input id="home-article-search" type="search" name="q" placeholder="Vide-greniers, compost, ateliers..." autocomplete="off">
            <button class="button primary" type="submit">Rechercher</button>
          </div>
        </form>
      </div>
    </section>

    <section class="section split">
      <div>
        <p class="eyebrow">{e(settings["home_about_eyebrow"])}</p>
        <h2>{e(settings["home_about_title"])}</h2>
      </div>
      <div class="lead home-description">
        {about_html}
      </div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">{e(settings["home_events_eyebrow"])}</p>
          <h2>{e(settings["home_events_title"])}</h2>
        </div>
        <a class="text-link" href="/agenda">{e(settings["home_events_link_label"])}</a>
      </div>
      <div class="card-grid">{event_html}</div>
    </section>

    <section class="section muted-band">
      <div class="section-heading">
        <div>
          <p class="eyebrow">{e(settings["home_articles_eyebrow"])}</p>
          <h2>{e(settings["home_articles_title"])}</h2>
        </div>
        <a class="text-link" href="/articles">{e(settings["home_articles_link_label"])}</a>
      </div>
      <div class="article-layout">{article_html}</div>
    </section>

    <section class="section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">{e(settings["home_photos_eyebrow"])}</p>
          <h2>{e(settings["home_photos_title"])}</h2>
        </div>
        <a class="text-link" href="/galerie">{e(settings["home_photos_link_label"])}</a>
      </div>
      {photo_html}
    </section>
    """
    return layout(
        "Accueil",
        body,
        "/",
        description=settings.get("seo_description") or about_text or settings["home_intro"],
        image_url=home_image,
        structured_data=[event_schema(row, settings) for row in events],
    )


def empty_state(message: str) -> str:
    return f'<div class="empty-state">{e(message)}</div>'


def render_photo_strip(rows: list[sqlite3.Row], settings: dict[str, str]) -> str:
    fallback_image = settings.get("home_image_url") or "/static/hero-garden.png"
    if not rows:
        return f"""
        <div class="photo-preview">
          <img src="{e(fallback_image)}" alt="">
          <div>
            <h3>{e(settings["home_photos_empty_title"])}</h3>
            <p>{e(settings["home_photos_empty_text"])}</p>
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
    settings = read_settings()
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
    return layout(
        "Agenda",
        body,
        "/agenda",
        description="Calendrier des ateliers, permanences et événements du jardin partagé Vert-Tige à Paris 14.",
        image_url=settings.get("seo_image_url"),
        structured_data=[event_schema(row, settings) for row in upcoming],
    )


def articles_page(query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    search_query = query.get("q", [""])[0].strip()
    with connect() as conn:
        all_rows = conn.execute(
            "SELECT * FROM articles WHERE published = 1 ORDER BY created_at DESC"
        ).fetchall()
    rows = filter_article_rows(all_rows, search_query)
    clear_link = '<a class="button secondary" href="/articles">Effacer</a>' if search_query else ""
    result_count = len(rows)
    result_label = "article trouvé" if result_count == 1 else "articles trouvés"
    search_summary = (
        f'<p class="search-summary">{result_count} {result_label} pour <strong>{e(search_query)}</strong>.</p>'
        if search_query
        else ""
    )
    empty_message = (
        f"Aucun article ne correspond à « {search_query} »."
        if search_query
        else "Aucun article publié."
    )
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Articles</p>
      <h1>Carnet de bord</h1>
      <p>Actualités, récits d’ateliers et nouvelles du jardin partagé.</p>
    </section>
    <section class="section">
      <form class="article-search" method="get" action="/articles" role="search" aria-label="Rechercher dans les articles">
        <label for="article-search">Rechercher un article</label>
        <div class="search-row">
          <input id="article-search" type="search" name="q" value="{e(search_query)}" placeholder="Atelier, compost, semis..." autocomplete="off">
          <button class="button primary" type="submit">Rechercher</button>
          {clear_link}
        </div>
      </form>
      {search_summary}
      <div class="article-layout">{"".join(article_card(row) for row in rows) or empty_state(empty_message)}</div>
    </section>
    """
    return layout(
        "Recherche d’articles" if search_query else "Articles",
        body,
        "/articles",
        description="Articles, actualités et récits des ateliers du jardin partagé Vert-Tige à Paris 14.",
        indexable=not bool(search_query),
    )


def article_page(slug: str) -> str:
    settings = read_settings()
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
    return layout(
        row["title"],
        body,
        f"/articles/{quote(row['slug'])}",
        description=row["summary"] or row["body"],
        image_url=image,
        og_type="article",
        structured_data=[article_schema(row, settings)],
    )


def gallery_page(query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    album_slug = query.get("album", [""])[0]
    with connect() as conn:
        albums = conn.execute(
            """
            SELECT a.*, COUNT(p.id) AS photo_count
            FROM photo_albums a
            LEFT JOIN photos p
              ON p.album_id = a.id AND p.visibility IN ('gallery', 'both')
            GROUP BY a.id
            ORDER BY a.name
            """
        ).fetchall()
        current_album = None
        params: tuple[object, ...] = ()
        where = "WHERE p.visibility IN ('gallery', 'both')"
        if album_slug:
            current_album = conn.execute(
                "SELECT * FROM photo_albums WHERE slug = ?",
                (album_slug,),
            ).fetchone()
            if current_album:
                where += " AND p.album_id = ?"
                params = (current_album["id"],)
        rows = conn.execute(
            f"""
            SELECT p.*, a.name AS album_name, a.slug AS album_slug
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            {where}
            ORDER BY p.created_at DESC
            """,
            params,
        ).fetchall()
    album_links = [
        f'<a class="album-filter {"is-active" if not album_slug else ""}" href="/galerie">Toutes</a>'
    ]
    album_links.extend(
        f'<a class="album-filter {"is-active" if album_slug == album["slug"] else ""}" href="/galerie?album={quote(album["slug"])}">{e(album["name"])} <span>{album["photo_count"]}</span></a>'
        for album in albums
    )
    if rows:
        items = "".join(
            f"""
            <figure class="photo-tile">
              <img src="/static/uploads/{e(row['filename'])}" alt="{e(row['title'] or 'Photo du jardin')}">
              <figcaption>
                <strong>{e(row['title'] or 'Photo du jardin')}</strong>
                <span>{e(row['caption'] or row['album_name'] or '')}</span>
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
      <h1>{e(current_album['name']) if current_album else 'Banque de photos'}</h1>
      <p>Un espace pour conserver et partager les images du jardin.</p>
    </section>
    <section class="section">
      <div class="album-filters">{"".join(album_links)}</div>
      <div class="photo-grid">{items}</div>
    </section>
    """
    gallery_description = (
        f"Album photo {current_album['name']} du jardin partagé Vert-Tige."
        if current_album
        else "Galerie photo du jardin partagé Vert-Tige à Paris 14."
    )
    canonical_path = f"/galerie?album={quote(current_album['slug'])}" if current_album else "/galerie"
    return layout(
        current_album["name"] if current_album else "Photos",
        body,
        canonical_path,
        description=gallery_description,
    )


def contact_page(sent: bool = False, saved: bool = False) -> str:
    settings = read_settings()
    if sent:
        success = '<div class="notice success">Message envoyé par email. Il est aussi conservé dans l’administration.</div>'
    elif saved:
        success = '<div class="notice warning">Message bien reçu et conservé dans l’administration. L’envoi email n’est pas encore configuré ou a échoué.</div>'
    else:
        success = ""
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
    return layout(
        "Contact",
        body,
        "/contact",
        track_conversion=sent,
        description="Contacter l’association Vert-Tige pour une question, une inscription ou une proposition d’atelier.",
    )


def practical_info_page() -> str:
    settings = read_settings()
    map_embed_url = settings.get("practical_map_embed_url", "").strip()
    map_link_url = settings.get("practical_map_link_url", "").strip()
    address = settings.get("practical_address") or "37 rue de Coulmiers, 75014 Paris"
    map_frame = (
        f"""
        <div class="external-content-placeholder" data-external-placeholder>
          <strong>Carte externe</strong>
          <p>La carte OpenStreetMap se charge depuis un service externe. Tu peux l’afficher en acceptant les contenus externes.</p>
          <button class="button primary" type="button" data-external-accept>Afficher la carte</button>
        </div>
          <iframe
            title="Carte du jardin Vert-Tige"
            data-consent-src="{e(map_embed_url)}"
            hidden
            loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"></iframe>
        """
        if map_embed_url
        else '<div class="map-placeholder">Carte à configurer depuis l’administration.</div>'
    )
    map_link = (
        f'<a class="button secondary" href="{e(map_link_url)}" target="_blank" rel="noopener noreferrer">Ouvrir l’itinéraire</a>'
        if map_link_url
        else ""
    )
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">{e(settings.get("practical_eyebrow"))}</p>
      <h1>{e(settings.get("practical_title"))}</h1>
      <p>{e(settings.get("practical_intro"))}</p>
    </section>
    <section class="section practical-layout">
      <article class="practical-map-card">
        <div class="map-frame" data-external-content>
          {map_frame}
        </div>
        <aside class="map-corner-card">
          <span>Adresse</span>
          <strong>{e(address)}</strong>
          <p>{e(settings.get("practical_opening"))}</p>
          {map_link}
        </aside>
      </article>
      <div class="practical-info-grid">
        <article class="practical-info-card featured">
          <span>Adresse</span>
          <strong>{e(address)}</strong>
        </article>
        <article class="practical-info-card">
          <span>Bus</span>
          <p>{e(settings.get("practical_bus"))}</p>
        </article>
        <article class="practical-info-card">
          <span>Métro</span>
          <p>{e(settings.get("practical_metro"))}</p>
        </article>
        <article class="practical-info-card">
          <span>Tram</span>
          <p>{e(settings.get("practical_tram"))}</p>
        </article>
        <article class="practical-info-card">
          <span>Vélib</span>
          <p>{e(settings.get("practical_velib"))}</p>
        </article>
        <article class="practical-info-card opening">
          <span>Ouverture au public</span>
          <p>{e(settings.get("practical_opening"))}</p>
        </article>
      </div>
    </section>
    """
    return layout(
        "Infos pratiques",
        body,
        "/infos-pratiques",
        description="Adresse, transports et horaires du jardin partagé Vert-Tige à Paris 14.",
        image_url=settings.get("seo_image_url"),
    )


def legal_page() -> str:
    settings = read_settings()
    legal_text = settings.get("legal_text", "").strip()
    extra = paragraphs(legal_text) if legal_text else "<p>Ces informations pourront être complétées avant la mise en ligne officielle.</p>"
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Cadre légal</p>
      <h1>Mentions légales</h1>
      <p>Informations relatives à l’édition et à l’hébergement du site.</p>
    </section>
    <section class="section legal-layout">
      <article class="legal-block">
        <h2>Éditeur du site</h2>
        <p><strong>{e(settings.get("legal_publisher") or settings["site_title"])}</strong></p>
        <p>Responsable de publication : {e(settings.get("legal_responsible") or "À compléter")}</p>
        <p>Contact : {e(settings.get("contact_email") or "À compléter")}</p>
      </article>
      <article class="legal-block">
        <h2>Hébergement</h2>
        <p>{e(settings.get("legal_hosting") or "À compléter")}</p>
      </article>
      <article class="legal-block">
        <h2>Informations complémentaires</h2>
        {extra}
      </article>
    </section>
    """
    return layout(
        "Mentions légales",
        body,
        "/mentions-legales",
        description="Mentions légales du site de l’association Vert-Tige.",
    )


def terms_page() -> str:
    settings = read_settings()
    terms_text = settings.get("terms_text", "").strip()
    content = paragraphs(terms_text) if terms_text else "<p>Les conditions générales d’utilisation pourront être complétées avant la mise en ligne officielle.</p>"
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Cadre d’utilisation</p>
      <h1>Conditions générales d’utilisation</h1>
      <p>Les règles de consultation et d’utilisation du site Vert-Tige.</p>
    </section>
    <section class="section legal-layout">
      <article class="legal-block">
        {content}
      </article>
    </section>
    """
    return layout(
        "Conditions générales d’utilisation",
        body,
        "/conditions-generales-utilisation",
        description="Conditions générales d’utilisation du site de l’association Vert-Tige.",
    )


def admin_shell(title: str, content: str, tab: str = "/admin") -> str:
    tabs = "".join(
        [
            nav_link("/admin", "Tableau de bord", tab),
            nav_link("/admin/home", "Accueil", tab),
            nav_link("/admin/practical", "Infos pratiques", tab),
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
    return layout(f"Admin - {title}", body, "/admin", indexable=False)


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
    return layout("Connexion admin", body, "/admin/login", indexable=False)


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
      <a class="admin-action" href="/admin/home"><strong>Page d’accueil</strong><span>Modifier le logo, le texte principal et le référencement.</span></a>
      <a class="admin-action" href="/admin/practical"><strong>Infos pratiques</strong><span>Mettre à jour l’adresse, les transports, la carte et les horaires.</span></a>
      <a class="admin-action" href="/admin/events/new"><strong>Nouvel événement</strong><span>Ajouter un atelier ou une permanence au calendrier.</span></a>
      <a class="admin-action" href="/admin/articles/new"><strong>Nouvel article</strong><span>Rédiger une actualité et choisir si elle est mise en avant.</span></a>
      <a class="admin-action" href="/admin/photos"><strong>Ajouter des photos</strong><span>Alimenter la banque d’images du jardin.</span></a>
    </div>
    <div class="notice warning">Avant une mise en ligne publique, remplace le mot de passe du compte référent, crée les comptes personnels nécessaires et configure <code>VERT_TIGE_SECRET</code>.</div>
    """
    return admin_shell("Tableau de bord", content, "/admin")


def admin_home_page() -> str:
    settings = read_settings()
    home_image_url = settings.get("home_image_url") or DEFAULT_SETTINGS["home_image_url"]
    home_image_preview = f'<img class="home-image-preview" src="{e(home_image_url)}" alt="Image principale actuelle" data-home-image-preview>'
    instagram_banner_image_url = settings.get("instagram_banner_image_url") or DEFAULT_SETTINGS["instagram_banner_image_url"]
    instagram_banner_preview = f'<img class="home-image-preview" src="{e(instagram_banner_image_url)}" alt="Image du bandeau Instagram" data-instagram-banner-preview>'
    with connect() as conn:
        library_photos = conn.execute(
            """
            SELECT p.*, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    library_options = photo_library_options(library_photos, home_image_url)
    instagram_library_options = photo_library_options(library_photos, instagram_banner_image_url)
    home_library_select = (
        f"""
          <label>Ou choisir dans la banque de photos
            <select name="home_image_choice" data-home-image-choice>
              <option value="">Conserver l’image actuelle</option>
              {library_options}
            </select>
          </label>
        """
        if library_options
        else '<p class="form-note">Ajoute d’abord des photos dans la banque de photos pour pouvoir les choisir ici.</p>'
    )
    instagram_library_select = (
        f"""
          <label>Ou choisir dans la banque de photos
            <select name="instagram_banner_image_choice" data-instagram-banner-choice>
              <option value="">Conserver l’image actuelle</option>
              {instagram_library_options}
            </select>
          </label>
        """
        if instagram_library_options
        else '<p class="form-note">Ajoute d’abord des photos dans la banque de photos pour pouvoir les choisir ici.</p>'
    )
    logo_preview = (
        f'<img class="logo-preview" src="{e(settings.get("logo_url"))}" alt="Logo actuel">'
        if settings.get("logo_url")
        else '<div class="logo-placeholder">VT</div>'
    )
    about_editor_html = editor_home_description(settings.get("home_about_text"))
    about_size_options = rich_text_size_options()
    analytics_provider = settings.get("analytics_provider", "")
    analytics_options = "".join(
        f'<option value="{value}" {"selected" if analytics_provider == value else ""}>{label}</option>'
        for value, label in [
            ("", "Aucun traceur"),
            ("plausible", "Plausible"),
            ("fathom", "Fathom"),
        ]
    )
    content = f"""
    <form class="form-panel" method="post" action="/admin/home" enctype="multipart/form-data">
      <nav class="admin-home-tabs" aria-label="Sous-navigation de la page d’accueil">
        <button class="admin-home-tab is-active" type="button" data-admin-home-tab="identity">Identité</button>
        <button class="admin-home-tab" type="button" data-admin-home-tab="texts">Textes</button>
        <button class="admin-home-tab" type="button" data-admin-home-tab="sections">Sections</button>
        <button class="admin-home-tab" type="button" data-admin-home-tab="social">Réseaux / footer</button>
        <button class="admin-home-tab" type="button" data-admin-home-tab="legal">Référencement / légal</button>
      </nav>
      <section class="admin-home-panel is-active" data-admin-home-panel="identity">
      <label>Nom du site<input name="site_title" value="{e(settings['site_title'])}" required></label>
      <label>Sous-titre<input name="tagline" value="{e(settings['tagline'])}" required></label>
      <div class="logo-editor">
        <div>
          <p class="field-label">Logo actuel</p>
          <div data-logo-preview>{logo_preview}</div>
        </div>
        <div>
          <input type="hidden" name="remove_logo" value="" data-logo-reset-field>
          <label>Nouveau logo<input type="file" name="logo_file" accept="image/*" data-logo-file></label>
          <button class="button small secondary" type="button" data-reset-logo>Retour à zéro</button>
        </div>
      </div>
      <div class="logo-editor">
        <div>
          <p class="field-label">Image principale actuelle</p>
          {home_image_preview}
        </div>
        <div>
          <input type="hidden" name="remove_home_image" value="" data-home-image-reset-field>
          <label>Nouvelle image principale<input type="file" name="home_image_file" accept="image/*" data-home-image-file></label>
          {home_library_select}
          <button class="button small secondary" type="button" data-reset-home-image data-default-src="{e(DEFAULT_SETTINGS['home_image_url'])}">Retour à zéro</button>
        </div>
      </div>
      </section>
      <section class="admin-home-panel" data-admin-home-panel="texts">
      <div class="settings-section">
        <h2>Bandeau principal</h2>
        <label>Petit titre<input name="home_hero_eyebrow" value="{e(settings.get('home_hero_eyebrow', ''))}"></label>
        <label>Phrase d’accroche<textarea name="home_intro" rows="3">{e(settings['home_intro'])}</textarea></label>
        <div class="form-row">
          <label>Bouton vers l’agenda<input name="home_primary_button_label" value="{e(settings.get('home_primary_button_label', ''))}"></label>
          <label>Bouton vers le contact<input name="home_secondary_button_label" value="{e(settings.get('home_secondary_button_label', ''))}"></label>
        </div>
        <p class="form-note">Le grand titre du bandeau reprend le nom du site renseigné plus haut.</p>
      </div>
      <div class="settings-section">
        <h2>Bloc de présentation</h2>
        <label>Petit titre<input name="home_about_eyebrow" value="{e(settings.get('home_about_eyebrow', ''))}"></label>
        <label>Titre du bloc<input name="home_about_title" value="{e(settings.get('home_about_title', ''))}"></label>
        <div class="description-format-panel" data-rich-editor-panel>
          <p class="field-label">Description</p>
          <div class="rich-text-toolbar" data-rich-toolbar aria-label="Mise en forme de la description">
            <button class="format-button" type="button" data-rich-command="bold" title="Gras"><strong>B</strong></button>
            <button class="format-button" type="button" data-rich-command="italic" title="Italique"><em>I</em></button>
            <button class="format-button" type="button" data-rich-command="underline" title="Souligné"><u>U</u></button>
            <label class="rich-size-select">Taille
              <select data-rich-size>{about_size_options}</select>
            </label>
          </div>
          <div class="rich-text-editor" contenteditable="true" role="textbox" aria-multiline="true" data-rich-editor>{about_editor_html}</div>
          <input type="hidden" name="home_about_text" value="{e(about_editor_html)}" data-rich-input>
        </div>
        <p class="form-note">Sélectionne un mot ou une phrase dans la description, puis applique le style souhaité.</p>
      </div>
      </section>
      <section class="admin-home-panel" data-admin-home-panel="sections">
      <div class="settings-section">
        <h2>Section agenda</h2>
        <div class="form-row">
          <label>Petit titre<input name="home_events_eyebrow" value="{e(settings.get('home_events_eyebrow', ''))}"></label>
          <label>Titre<input name="home_events_title" value="{e(settings.get('home_events_title', ''))}"></label>
        </div>
        <div class="form-row">
          <label>Lien<input name="home_events_link_label" value="{e(settings.get('home_events_link_label', ''))}"></label>
          <label>Message si aucun événement<input name="home_events_empty" value="{e(settings.get('home_events_empty', ''))}"></label>
        </div>
      </div>
      <div class="settings-section">
        <h2>Section articles</h2>
        <div class="form-row">
          <label>Petit titre<input name="home_articles_eyebrow" value="{e(settings.get('home_articles_eyebrow', ''))}"></label>
          <label>Titre<input name="home_articles_title" value="{e(settings.get('home_articles_title', ''))}"></label>
        </div>
        <div class="form-row">
          <label>Lien<input name="home_articles_link_label" value="{e(settings.get('home_articles_link_label', ''))}"></label>
          <label>Message si aucun article<input name="home_articles_empty" value="{e(settings.get('home_articles_empty', ''))}"></label>
        </div>
      </div>
      <div class="settings-section">
        <h2>Section photos</h2>
        <div class="form-row">
          <label>Petit titre<input name="home_photos_eyebrow" value="{e(settings.get('home_photos_eyebrow', ''))}"></label>
          <label>Titre<input name="home_photos_title" value="{e(settings.get('home_photos_title', ''))}"></label>
        </div>
        <label>Lien<input name="home_photos_link_label" value="{e(settings.get('home_photos_link_label', ''))}"></label>
        <div class="form-row">
          <label>Titre si aucune photo<input name="home_photos_empty_title" value="{e(settings.get('home_photos_empty_title', ''))}"></label>
          <label>Texte si aucune photo<input name="home_photos_empty_text" value="{e(settings.get('home_photos_empty_text', ''))}"></label>
        </div>
      </div>
      </section>
      <section class="admin-home-panel" data-admin-home-panel="social">
      <div class="settings-section">
        <h2>Réseaux sociaux</h2>
        <div class="form-row">
          <label>Facebook<input type="url" name="facebook_url" value="{e(settings.get('facebook_url', ''))}" placeholder="https://www.facebook.com/..."></label>
          <label>Instagram<input type="url" name="instagram_url" value="{e(settings.get('instagram_url', ''))}" placeholder="https://www.instagram.com/..."></label>
        </div>
      </div>
      <div class="settings-section">
        <h2>Bandeau Instagram avant footer</h2>
        <label>Texte affiché<input name="instagram_banner_text" value="{e(settings.get('instagram_banner_text', ''))}"></label>
        <div class="logo-editor">
          <div>
            <p class="field-label">Image actuelle</p>
            {instagram_banner_preview}
          </div>
          <div>
            <input type="hidden" name="remove_instagram_banner_image" value="" data-instagram-banner-reset-field>
            <label>Nouvelle image<input type="file" name="instagram_banner_image_file" accept="image/*" data-instagram-banner-file></label>
            {instagram_library_select}
            <button class="button small secondary" type="button" data-reset-instagram-banner data-default-src="{e(DEFAULT_SETTINGS['instagram_banner_image_url'])}">Retour à zéro</button>
          </div>
        </div>
        <p class="form-note">L’image entière devient cliquable vers l’adresse Instagram configurée plus haut.</p>
      </div>
      <div class="settings-section">
        <h2>Footer</h2>
        <div class="form-row">
          <label>Adresse<input name="footer_address" value="{e(settings.get('footer_address', ''))}"></label>
          <label>Copyright<input name="footer_copyright" value="{e(settings.get('footer_copyright', ''))}"></label>
        </div>
      </div>
      </section>
      <section class="admin-home-panel" data-admin-home-panel="legal">
      <div class="settings-section">
        <h2>Référencement</h2>
        <label>URL publique du site<input type="url" name="site_url" value="{e(settings.get('site_url', ''))}" placeholder="https://www.vert-tige.fr"></label>
        <label>Description pour Google<textarea name="seo_description" rows="4">{e(settings.get('seo_description', ''))}</textarea></label>
        <label>Validation Google Search Console<input name="google_site_verification" value="{e(settings.get('google_site_verification', ''))}" placeholder="Code fourni par Google"></label>
        <p class="form-note">Ces champs alimentent les titres, descriptions, aperçus de partage, <code>sitemap.xml</code> et la balise de validation Google.</p>
      </div>
      <div class="settings-section">
        <h2>Mentions légales</h2>
        <label>Éditeur du site<input name="legal_publisher" value="{e(settings.get('legal_publisher', ''))}"></label>
        <label>Responsable de publication<input name="legal_responsible" value="{e(settings.get('legal_responsible', ''))}"></label>
        <label>Hébergeur<textarea name="legal_hosting" rows="4">{e(settings.get('legal_hosting', ''))}</textarea></label>
        <label>Texte complémentaire<textarea name="legal_text" rows="7">{e(settings.get('legal_text', ''))}</textarea></label>
        <label>Conditions générales d’utilisation<textarea name="terms_text" rows="7">{e(settings.get('terms_text', ''))}</textarea></label>
      </div>
      <div class="settings-section">
        <h2>Google Ads</h2>
        <div class="form-row">
          <label>ID Google Ads<input name="google_ads_id" value="{e(settings.get('google_ads_id', ''))}" placeholder="AW-XXXXXXXXXX"></label>
          <label>Libellé de conversion contact<input name="google_ads_conversion_label" value="{e(settings.get('google_ads_conversion_label', ''))}"></label>
        </div>
        <p class="form-note">Ces champs préparent le tag Google Ads, chargé uniquement après acceptation des cookies.</p>
      </div>
      <div class="settings-section">
        <h2>Statistiques de fréquentation</h2>
        <div class="form-row">
          <label>Outil
            <select name="analytics_provider">{analytics_options}</select>
          </label>
          <label>Identifiant du site<input name="analytics_site_id" value="{e(settings.get('analytics_site_id', ''))}" placeholder="Domaine Plausible ou Site ID Fathom"></label>
        </div>
        <p class="form-note">Plausible et Fathom peuvent fonctionner sans cookies. Le script reste soumis au choix du visiteur dans cette base.</p>
      </div>
      </section>
      <button class="button primary" type="submit">Enregistrer</button>
    </form>
    """
    return admin_shell("Page d’accueil", content, "/admin/home")


def admin_practical_page() -> str:
    settings = read_settings()
    content = f"""
    <form class="form-panel" method="post" action="/admin/practical">
      <div class="settings-section">
        <h2>En-tête</h2>
        <label>Petit titre<input name="practical_eyebrow" value="{e(settings.get('practical_eyebrow', ''))}"></label>
        <label>Titre<input name="practical_title" value="{e(settings.get('practical_title', ''))}"></label>
        <label>Introduction<textarea name="practical_intro" rows="3">{e(settings.get('practical_intro', ''))}</textarea></label>
      </div>
      <div class="settings-section">
        <h2>Adresse et carte</h2>
        <label>Adresse<input name="practical_address" value="{e(settings.get('practical_address', ''))}"></label>
        <label>URL de carte intégrée<textarea name="practical_map_embed_url" rows="3">{e(settings.get('practical_map_embed_url', ''))}</textarea></label>
        <label>Lien d’itinéraire<input type="url" name="practical_map_link_url" value="{e(settings.get('practical_map_link_url', ''))}"></label>
        <p class="form-note">La carte intégrée peut être un lien d’intégration OpenStreetMap. Le lien d’itinéraire ouvre la carte dans un nouvel onglet.</p>
      </div>
      <div class="settings-section">
        <h2>Transports</h2>
        <label>Bus<input name="practical_bus" value="{e(settings.get('practical_bus', ''))}"></label>
        <label>Métro<input name="practical_metro" value="{e(settings.get('practical_metro', ''))}"></label>
        <label>Tram<input name="practical_tram" value="{e(settings.get('practical_tram', ''))}"></label>
        <label>Vélib<input name="practical_velib" value="{e(settings.get('practical_velib', ''))}"></label>
      </div>
      <div class="settings-section">
        <h2>Ouverture</h2>
        <label>Horaires<textarea name="practical_opening" rows="3">{e(settings.get('practical_opening', ''))}</textarea></label>
      </div>
      <button class="button primary" type="submit">Enregistrer</button>
    </form>
    """
    return admin_shell("Infos pratiques", content, "/admin/practical")


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
        albums = conn.execute("SELECT * FROM photo_albums ORDER BY name").fetchall()
        rows = conn.execute(
            """
            SELECT p.*, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    album_list = "".join(
        f"""
        <tr>
          <td><strong>{e(album['name'])}</strong><span>/{e(album['slug'])}</span></td>
          <td>{e(album['description'] or '')}</td>
          <td class="actions">
            <form method="post" action="/admin/photos/albums/{album['id']}/delete"><button class="button small danger" type="submit">Supprimer</button></form>
          </td>
        </tr>
        """
        for album in albums
    )
    items = "".join(
        f"""
        <figure class="photo-tile">
          <img src="/static/uploads/{e(row['filename'])}" alt="{e(row['title'] or 'Photo du jardin')}">
          <figcaption>
            <strong>{e(row['title'] or 'Photo du jardin')}</strong>
            <span>{e(row['caption'] or row['album_name'] or '')}</span>
            <em>{e(row['album_name'] or 'Sans album')}</em>
            <em>{e(photo_visibility_label(row['visibility']))}</em>
            <form class="inline-photo-form" method="post" action="/admin/photos/{row['id']}/visibility">
              <select name="album_id">{album_options(albums, row['album_id'])}</select>
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
    <div class="admin-two-column">
      <form class="form-panel" method="post" action="/admin/photos/albums/create">
        <h2>Créer un album</h2>
        <label>Nom de l’album<input name="name" required></label>
        <label>Description<textarea name="description" rows="3"></textarea></label>
        <button class="button primary" type="submit">Créer l’album</button>
      </form>
      <table class="admin-table albums-table">
        <thead><tr><th>Album</th><th>Description</th><th></th></tr></thead>
        <tbody>{album_list or '<tr><td colspan="3">Aucun album.</td></tr>'}</tbody>
      </table>
    </div>
    <form class="form-panel" method="post" action="/admin/photos/upload" enctype="multipart/form-data">
      <h2>Ajouter une photo</h2>
      <label>Image<input type="file" name="photo" accept="image/*" required></label>
      <label>Titre<input name="title"></label>
      <label>Légende<textarea name="caption" rows="4"></textarea></label>
      <label>Album
        <select name="album_id">{album_options(albums, albums[0]['id'] if albums else None)}</select>
      </label>
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
    settings = read_settings()
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
          <div class="message-actions">
            <form method="post" action="/admin/messages/{row['id']}/toggle">
              <button class="button small secondary" type="submit">{'Marquer à traiter' if row['handled'] else 'Marquer traité'}</button>
            </form>
            {f'<form method="post" action="/admin/messages/{row["id"]}/delete"><button class="button small danger" type="submit">Supprimer</button></form>' if row['handled'] else ''}
          </div>
        </article>
        """
        for row in rows
    )
    content = f"""
    {messaging_settings_form(settings)}
    <div class="section-heading admin-section-heading">
      <div>
        <p class="eyebrow">Messages reçus</p>
        <h2>Formulaire de contact</h2>
      </div>
    </div>
    <div class="list-stack">{items or empty_state("Aucun message.")}</div>
    """
    return admin_shell("Messages", content, "/admin/messages")


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


def robots_txt() -> str:
    settings = read_settings()
    return "\n".join(
        [
            "User-agent: *",
            "Disallow: /admin",
            "Disallow: /admin/",
            "Allow: /",
            f"Sitemap: {absolute_url('/sitemap.xml', settings)}",
            "",
        ]
    )


def sitemap_entry(
    location: str,
    settings: dict[str, str],
    lastmod: str = "",
    changefreq: str = "",
    priority: str = "",
) -> str:
    parts = [f"    <loc>{e(absolute_url(location, settings))}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{e(lastmod[:10])}</lastmod>")
    if changefreq:
        parts.append(f"    <changefreq>{e(changefreq)}</changefreq>")
    if priority:
        parts.append(f"    <priority>{e(priority)}</priority>")
    return "  <url>\n" + "\n".join(parts) + "\n  </url>"


def sitemap_xml() -> str:
    settings = read_settings()
    entries = [
        sitemap_entry("/", settings, changefreq="weekly", priority="1.0"),
        sitemap_entry("/agenda", settings, changefreq="weekly", priority="0.8"),
        sitemap_entry("/articles", settings, changefreq="weekly", priority="0.8"),
        sitemap_entry("/galerie", settings, changefreq="monthly", priority="0.7"),
        sitemap_entry("/infos-pratiques", settings, changefreq="yearly", priority="0.6"),
        sitemap_entry("/contact", settings, changefreq="yearly", priority="0.5"),
        sitemap_entry("/mentions-legales", settings, changefreq="yearly", priority="0.3"),
        sitemap_entry("/conditions-generales-utilisation", settings, changefreq="yearly", priority="0.3"),
    ]
    with connect() as conn:
        articles = conn.execute(
            "SELECT slug, updated_at FROM articles WHERE published = 1 ORDER BY updated_at DESC"
        ).fetchall()
        albums = conn.execute(
            """
            SELECT a.slug, MAX(p.created_at) AS updated_at
            FROM photo_albums a
            JOIN photos p ON p.album_id = a.id AND p.visibility IN ('gallery', 'both')
            GROUP BY a.id
            ORDER BY a.name
            """
        ).fetchall()
    entries.extend(
        sitemap_entry(f"/articles/{quote(row['slug'])}", settings, row["updated_at"], "monthly", "0.7")
        for row in articles
    )
    entries.extend(
        sitemap_entry(f"/galerie?album={quote(row['slug'])}", settings, row["updated_at"], "monthly", "0.5")
        for row in albums
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def not_found_page() -> str:
    body = """
    <section class="page-hero compact-hero">
      <p class="eyebrow">404</p>
      <h1>Page introuvable</h1>
      <p>La page demandée n’existe pas ou a été déplacée.</p>
      <a class="button primary" href="/">Retour à l’accueil</a>
    </section>
    """
    return layout("Page introuvable", body, "/", indexable=False)


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
    album_id: int | None = None,
) -> str | None:
    if not upload or not upload.data or len(upload.data) > MAX_UPLOAD_BYTES:
        return None
    filename = safe_upload_name(upload.filename)
    (UPLOAD_DIR / filename).write_bytes(upload.data)
    conn.execute(
        "INSERT INTO photos (album_id, filename, title, caption, visibility, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (album_id, filename, title, caption, normalize_photo_visibility(visibility), now_iso()),
    )
    return f"/static/uploads/{filename}"


def save_logo_upload(upload: Upload) -> str | None:
    if not upload or not upload.data or len(upload.data) > MAX_UPLOAD_BYTES:
        return None
    filename = safe_upload_name(f"logo-{upload.filename}")
    (UPLOAD_DIR / filename).write_bytes(upload.data)
    return f"/static/uploads/{filename}"


def save_home_image_upload(upload: Upload) -> str | None:
    if not upload or not upload.data or len(upload.data) > MAX_UPLOAD_BYTES:
        return None
    filename = safe_upload_name(f"accueil-{upload.filename}")
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
    settings = read_settings()
    smtp_enabled = settings.get("smtp_enabled") == "1" or bool(os.getenv("VERT_TIGE_SMTP_HOST"))
    host = os.getenv("VERT_TIGE_SMTP_HOST") or settings.get("smtp_host", "").strip()
    recipient = CONTACT_TO or settings.get("smtp_to", "").strip() or settings.get("contact_email", "").strip()
    if not smtp_enabled or not host or not recipient:
        return False

    raw_port = os.getenv("VERT_TIGE_SMTP_PORT") or settings.get("smtp_port", "587")
    try:
        port = int(raw_port)
    except ValueError:
        write_log(f"Email non envoyé : port SMTP invalide ({raw_port}).")
        return False
    security = normalize_smtp_security(os.getenv("VERT_TIGE_SMTP_SECURITY") or settings.get("smtp_security"))
    smtp_user = os.getenv("VERT_TIGE_SMTP_USER") or settings.get("smtp_user", "").strip()
    smtp_password = os.getenv("VERT_TIGE_SMTP_PASSWORD") or settings.get("smtp_password", "")
    smtp_from = (
        os.getenv("VERT_TIGE_SMTP_FROM")
        or settings.get("smtp_from", "").strip()
        or smtp_user
        or recipient
    )

    message = EmailMessage()
    subject = form.get("subject", "").strip() or "Message depuis le site Vert-Tige"
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipient
    if form.get("email"):
        message["Reply-To"] = form["email"]
    message.set_content(
        "Message reçu depuis le formulaire de contact du site Vert-Tige.\n\n"
        f"Nom : {form.get('name', '')}\n"
        f"Email : {form.get('email', '')}\n"
        f"Sujet : {subject}\n\n"
        f"{form.get('body', '')}"
    )

    try:
        if security == "ssl":
            with smtplib.SMTP_SSL(host, port, timeout=10) as smtp:
                if smtp_user:
                    smtp.login(smtp_user, smtp_password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                if security == "starttls":
                    smtp.starttls()
                if smtp_user:
                    smtp.login(smtp_user, smtp_password)
                smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        write_log(f"Email non envoyé : {exc}")
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
        elif path == "/robots.txt":
            self.respond_text(robots_txt(), content_type="text/plain; charset=utf-8")
        elif path == "/sitemap.xml":
            self.respond_text(sitemap_xml(), content_type="application/xml; charset=utf-8")
        elif path == "/agenda":
            self.respond_html(agenda_page(query))
        elif path == "/articles":
            self.respond_html(articles_page(query))
        elif path.startswith("/articles/"):
            self.respond_html(article_page(unquote(path.removeprefix("/articles/"))))
        elif path == "/galerie":
            self.respond_html(gallery_page(query))
        elif path == "/infos-pratiques":
            self.respond_html(practical_info_page())
        elif path == "/contact":
            self.respond_html(
                contact_page(sent=query.get("sent") == ["1"], saved=query.get("saved") == ["1"])
            )
        elif path == "/mentions-legales":
            self.respond_html(legal_page())
        elif path == "/conditions-generales-utilisation":
            self.respond_html(terms_page())
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
        elif path == "/admin/practical":
            self.respond_html(admin_practical_page())
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
        elif path == "/admin/practical":
            self.save_practical()
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
        elif path == "/admin/photos/albums/create":
            self.create_photo_album()
        elif match := re.fullmatch(r"/admin/photos/albums/(\d+)/delete", path):
            self.delete_photo_album(int(match.group(1)))
        elif path == "/admin/photos/upload":
            self.upload_photo()
        elif match := re.fullmatch(r"/admin/photos/(\d+)/visibility", path):
            self.update_photo_visibility(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/photos/(\d+)/delete", path):
            self.delete_photo(int(match.group(1)))
        elif path == "/admin/messages/settings":
            self.save_messaging_settings()
        elif match := re.fullmatch(r"/admin/messages/(\d+)/delete", path):
            self.delete_message(int(match.group(1)))
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
        allowed = [
            "site_title",
            "tagline",
            "home_intro",
            "home_about_text",
            "home_image_url",
            "home_hero_eyebrow",
            "home_primary_button_label",
            "home_secondary_button_label",
            "home_about_eyebrow",
            "home_about_title",
            "home_events_eyebrow",
            "home_events_title",
            "home_events_link_label",
            "home_events_empty",
            "home_articles_eyebrow",
            "home_articles_title",
            "home_articles_link_label",
            "home_articles_empty",
            "home_photos_eyebrow",
            "home_photos_title",
            "home_photos_link_label",
            "home_photos_empty_title",
            "home_photos_empty_text",
            "logo_url",
            "facebook_url",
            "instagram_url",
            "footer_address",
            "footer_copyright",
            "instagram_banner_text",
            "instagram_banner_image_url",
            "legal_publisher",
            "legal_responsible",
            "legal_hosting",
            "legal_text",
            "terms_text",
            "google_ads_id",
            "google_ads_conversion_label",
            "analytics_provider",
            "analytics_site_id",
            "site_url",
            "seo_description",
            "google_site_verification",
        ]
        if not valid_optional_url(form.get("facebook_url", "").strip()) or not valid_optional_url(form.get("instagram_url", "").strip()):
            self.redirect("/admin/home")
            return
        if not valid_optional_url(form.get("site_url", "").strip()):
            self.redirect("/admin/home")
            return
        if form.get("analytics_provider", "").strip() not in {"", "plausible", "fathom"}:
            self.redirect("/admin/home")
            return
        current_settings = read_settings()
        current_logo = current_settings.get("logo_url", "")
        current_home_image = current_settings.get("home_image_url") or DEFAULT_SETTINGS["home_image_url"]
        current_instagram_banner_image = (
            current_settings.get("instagram_banner_image_url") or DEFAULT_SETTINGS["instagram_banner_image_url"]
        )
        remove_logo = form.get("remove_logo") == "1"
        remove_home_image = form.get("remove_home_image") == "1"
        remove_instagram_banner_image = form.get("remove_instagram_banner_image") == "1"
        logo_url = "" if remove_logo else current_logo
        home_image_url = DEFAULT_SETTINGS["home_image_url"] if remove_home_image else current_home_image
        instagram_banner_image_url = (
            DEFAULT_SETTINGS["instagram_banner_image_url"]
            if remove_instagram_banner_image
            else current_instagram_banner_image
        )
        home_image_choice = existing_photo_upload_url(form.get("home_image_choice"))
        if home_image_choice and not remove_home_image:
            home_image_url = home_image_choice
        instagram_banner_image_choice = existing_photo_upload_url(form.get("instagram_banner_image_choice"))
        if instagram_banner_image_choice and not remove_instagram_banner_image:
            instagram_banner_image_url = instagram_banner_image_choice
        logo_file = files.get("logo_file")
        if logo_file and logo_file.data and not remove_logo:
            try:
                uploaded_logo = save_logo_upload(logo_file)
            except ValueError:
                uploaded_logo = None
            if uploaded_logo:
                logo_url = uploaded_logo
        home_image_file = files.get("home_image_file")
        if home_image_file and home_image_file.data and not remove_home_image:
            try:
                uploaded_home_image = save_home_image_upload(home_image_file)
            except ValueError:
                uploaded_home_image = None
            if uploaded_home_image:
                home_image_url = uploaded_home_image
        instagram_banner_image_file = files.get("instagram_banner_image_file")
        if instagram_banner_image_file and instagram_banner_image_file.data and not remove_instagram_banner_image:
            try:
                uploaded_instagram_banner_image = save_home_image_upload(instagram_banner_image_file)
            except ValueError:
                uploaded_instagram_banner_image = None
            if uploaded_instagram_banner_image:
                instagram_banner_image_url = uploaded_instagram_banner_image
        with connect() as conn:
            for key in allowed:
                if key == "logo_url":
                    value = logo_url
                elif key == "home_image_url":
                    value = home_image_url
                elif key == "instagram_banner_image_url":
                    value = instagram_banner_image_url
                elif key == "home_about_text":
                    value = sanitize_rich_text(form.get(key, ""))
                elif key == "analytics_provider":
                    value = form.get(key, "").strip()
                else:
                    value = form.get(key, "").strip()
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
        self.redirect("/admin/home")

    def save_practical(self) -> None:
        form, _files = self.read_form()
        allowed = [
            "practical_eyebrow",
            "practical_title",
            "practical_intro",
            "practical_address",
            "practical_map_embed_url",
            "practical_map_link_url",
            "practical_bus",
            "practical_metro",
            "practical_tram",
            "practical_velib",
            "practical_opening",
        ]
        map_embed_url = form.get("practical_map_embed_url", "").strip()
        map_link_url = form.get("practical_map_link_url", "").strip()
        if (map_embed_url and not valid_optional_url(map_embed_url)) or (
            map_link_url and not valid_optional_url(map_link_url)
        ):
            self.redirect("/admin/practical")
            return
        with connect() as conn:
            for key in allowed:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, form.get(key, "").strip()),
                )
        self.redirect("/admin/practical")

    def save_messaging_settings(self) -> None:
        form, _ = self.read_form()
        allowed = [
            "contact_email",
            "smtp_enabled",
            "smtp_host",
            "smtp_port",
            "smtp_security",
            "smtp_user",
            "smtp_password",
            "smtp_from",
            "smtp_to",
        ]
        contact_email = form.get("contact_email", "").strip()
        if contact_email and not valid_email(contact_email):
            self.redirect("/admin/messages")
            return
        if form.get("smtp_enabled") == "1":
            smtp_to = form.get("smtp_to", "").strip()
            smtp_from = form.get("smtp_from", "").strip()
            smtp_port = form.get("smtp_port", "").strip()
            if (
                not form.get("smtp_host", "").strip()
                or not smtp_to
                or not valid_email(smtp_to)
                or (smtp_from and not valid_email(smtp_from))
                or not valid_port(smtp_port)
            ):
                self.redirect("/admin/messages")
                return
        current_settings = read_settings()
        with connect() as conn:
            for key in allowed:
                if key == "smtp_enabled":
                    value = "1" if form.get("smtp_enabled") == "1" else ""
                elif key == "smtp_security":
                    value = normalize_smtp_security(form.get("smtp_security"))
                elif key == "smtp_password" and not form.get("smtp_password", ""):
                    value = current_settings.get("smtp_password", "")
                else:
                    value = form.get(key, "").strip()
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )
        self.redirect("/admin/messages")

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
                        int_or_none(form.get("album_id")),
                    )
            except ValueError:
                self.redirect("/admin/photos")
                return
        self.redirect("/admin/photos")

    def update_photo_visibility(self, photo_id: int) -> None:
        form, _ = self.read_form()
        visibility = normalize_photo_visibility(form.get("visibility"))
        album_id = int_or_none(form.get("album_id"))
        with connect() as conn:
            conn.execute(
                "UPDATE photos SET visibility = ?, album_id = ? WHERE id = ?",
                (visibility, album_id, photo_id),
            )
        self.redirect("/admin/photos")

    def create_photo_album(self) -> None:
        form, _ = self.read_form()
        name = form.get("name", "").strip()
        if not name:
            self.redirect("/admin/photos")
            return
        with connect() as conn:
            slug = unique_album_slug(conn, name)
            try:
                conn.execute(
                    "INSERT INTO photo_albums (name, slug, description, created_at) VALUES (?, ?, ?, ?)",
                    (name, slug, form.get("description", "").strip(), now_iso()),
                )
            except sqlite3.IntegrityError:
                pass
        self.redirect("/admin/photos")

    def delete_photo_album(self, album_id: int) -> None:
        with connect() as conn:
            default_album = conn.execute(
                "SELECT id FROM photo_albums WHERE id != ? ORDER BY id LIMIT 1",
                (album_id,),
            ).fetchone()
            if default_album is None:
                self.redirect("/admin/photos")
                return
            conn.execute(
                "UPDATE photos SET album_id = ? WHERE album_id = ?",
                (default_album["id"], album_id),
            )
            conn.execute("DELETE FROM photo_albums WHERE id = ?", (album_id,))
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
        email_sent = send_contact_email(form)
        self.redirect("/contact?sent=1" if email_sent else "/contact?saved=1")

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
                session_cookie_header(session_value(user["id"]), SESSION_MAX_AGE_SECONDS),
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
            session_cookie_header("", 0),
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

    def delete_message(self, message_id: int) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM messages WHERE id = ? AND handled = 1", (message_id,))
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
        nonce = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        content = content.replace(CSP_NONCE_PLACEHOLDER, nonce)
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://www.googletagmanager.com https://plausible.io https://cdn.usefathom.com; "
            "connect-src 'self' https://www.google-analytics.com https://www.googletagmanager.com https://googleads.g.doubleclick.net https://plausible.io https://api.usefathom.com; "
            "img-src 'self' data: https://www.google.com https://www.google.fr https://googleads.g.doubleclick.net; "
            "frame-src https://www.openstreetmap.org; "
            "style-src 'self'; form-action 'self'",
        )
        self.end_headers()
        self.wfile.write(data)

    def respond_text(self, content: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
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
