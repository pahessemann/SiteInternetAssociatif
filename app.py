from __future__ import annotations

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
import zipfile
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
BACKUP_DIR = DATA_DIR / "backups"
LOG_PATH = BASE_DIR / "server.log"
CSP_NONCE_PLACEHOLDER = "__VERT_TIGE_CSP_NONCE__"
BACKUP_NAME_RE = re.compile(r"^vert-tige-backup-\d{8}-\d{6}\.zip$")

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
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
PHOTO_VISIBILITY_LABELS = {
    "gallery": "Galerie uniquement",
    "article": "Articles uniquement",
    "both": "Galerie + articles",
    "library": "Bibliothèque uniquement",
}
CHRISTMAS_CATEGORY_LABELS = {
    "recette": "Recette",
    "jardin": "Conseil jardinage",
    "nature": "Nature",
    "atelier": "Atelier créatif",
    "ecogeste": "Écogeste",
    "histoire": "Histoire du jardin",
    "surprise": "Surprise",
}
CHRISTMAS_ACCENT_DEFAULT = "#a62f2f"
CHRISTMAS_DEFAULT_IMAGE = "/static/noel-jardin-hiver-2026.png"
CHRISTMAS_COMPLETION_TITLE_DEFAULT = "Bravo, vous avez complété le calendrier !"
CHRISTMAS_COMPLETION_MESSAGE_DEFAULT = (
    "Vous avez découvert les 24 surprises du jardin. Toute l’équipe de "
    "l’association vous souhaite de très belles fêtes !"
)
CHRISTMAS_COMPLETION_LINK_LABEL_DEFAULT = "Découvrir la surprise"
DEFAULT_CHRISTMAS_DAYS = [
    ("jardin", "Préparer le jardin à l’hiver", "Trois gestes simples avant les grands froids.", "Pailler les parcelles nues, protéger les pots fragiles et laisser quelques tiges creuses debout : elles serviront de refuge aux insectes pendant l’hiver."),
    ("recette", "Velouté de courge rôtie", "Une soupe douce et chaleureuse.", "Rôtir une courge avec un oignon et un filet d’huile pendant 35 minutes à 190 °C. Mixer avec du bouillon chaud, une pincée de muscade et un peu de crème ou de lait végétal."),
    ("nature", "Observer les oiseaux", "Un mini-défi à faire depuis la fenêtre.", "Pendant dix minutes, noter les oiseaux aperçus. Mésange, rouge-gorge ou merle : leurs visites racontent déjà beaucoup sur la biodiversité du quartier."),
    ("atelier", "Étoiles en papier récupéré", "Une décoration zéro déchet.", "Découper des bandes dans un ancien magazine, les plier en accordéon puis réunir les extrémités. Une ficelle suffit pour suspendre chaque étoile."),
    ("ecogeste", "Bien nourrir les oiseaux", "Les bons aliments, au bon moment.", "En période de gel, proposer des graines de tournesol et de l’eau propre. Éviter le pain et les aliments salés, peu adaptés à leur organisme."),
    ("recette", "Pommes au four", "Un dessert de saison presque sans vaisselle.", "Évider les pommes, ajouter quelques noix, de la cannelle et une cuillère de miel. Cuire 25 minutes à 180 °C avec un fond d’eau dans le plat."),
    ("jardin", "Récolter la mâche", "Une salade qui aime le froid.", "Couper les rosettes juste au-dessus du collet pour préserver les jeunes feuilles. Récolter de préférence par temps sec et rincer au dernier moment."),
    ("histoire", "Le jardin en hiver", "Pourquoi le repos fait partie du cycle.", "Sous la surface, la vie continue : racines, champignons et micro-organismes transforment lentement la matière. Le calme de décembre prépare déjà le printemps."),
    ("atelier", "Une mangeoire en pomme de pin", "Une activité facile à partager avec les enfants.", "Attacher une ficelle à une pomme de pin, glisser un mélange de graisse végétale non salée et de graines entre les écailles, puis suspendre hors de portée des chats."),
    ("recette", "Tisane pomme-romarin", "Le jardin s’invite dans une boisson chaude.", "Faire frémir quelques pelures de pomme bio avec une petite branche de romarin pendant 8 minutes. Filtrer puis ajouter un peu de miel selon le goût."),
    ("jardin", "Planifier les semis", "Quelques lignes aujourd’hui, du temps gagné au printemps.", "Lister les variétés qui ont bien poussé, les quantités utiles et les dates de semis. Garder une place pour une nouveauté et une autre pour les fleurs mellifères."),
    ("ecogeste", "Emballages en tissu", "Le furoshiki remplace le papier cadeau.", "Un carré de tissu, un foulard ou une jolie chute de coton se noue autour du cadeau. Le tissu pourra être réutilisé l’année suivante."),
    ("nature", "La lune et le jardin", "Lever les yeux avant de rentrer.", "Repérer la phase de la lune ce soir et observer sa position. Ce rendez-vous quotidien aide à suivre le ciel, sans avoir besoin d’un instrument."),
    ("recette", "Pesto de fanes", "Une idée anti-gaspillage colorée.", "Mixer des fanes bien lavées avec des noix, de l’ail, un fromage sec et de l’huile. Ajuster la texture avec un peu d’eau et servir sur des tartines."),
    ("jardin", "Nettoyer sans tout enlever", "Conserver des abris pour la petite faune.", "Retirer seulement les végétaux malades. Garder feuilles, tiges et brindilles dans un coin calme : ils protègent le sol et de nombreux auxiliaires."),
    ("atelier", "Marque-places végétaux", "Une table de fête inspirée du jardin.", "Écrire les prénoms sur de petits cartons et glisser une branche de romarin, une feuille persistante ou une baie décorative sous une ficelle naturelle."),
    ("recette", "Sablés aux herbes", "Une version salée pour l’apéritif.", "Mélanger farine, beurre, fromage râpé et herbes séchées. Former un rouleau, laisser reposer au frais, découper puis cuire 12 minutes à 180 °C."),
    ("ecogeste", "Un compost équilibré", "Même en hiver, le compost a besoin d’air.", "Alterner les déchets humides avec des matières brunes : feuilles sèches, petits cartons non imprimés ou brindilles broyées. Mélanger légèrement sans tasser."),
    ("nature", "Reconnaître un bourgeon", "Le printemps est déjà en préparation.", "Observer la forme, la couleur et la disposition des bourgeons sur un rameau. Photographier sans cueillir, puis comparer au retour des feuilles."),
    ("recette", "Chutney de saison", "Un condiment pour transformer les fruits mûrs.", "Cuire doucement pommes ou poires avec oignon, vinaigre, sucre et épices jusqu’à obtenir une compotée. Conserver au frais dans un pot propre."),
    ("jardin", "Prendre soin des outils", "Dix minutes pour prolonger leur durée de vie.", "Brosser la terre sèche, affûter prudemment les lames puis huiler les parties métalliques et les manches en bois avant de ranger au sec."),
    ("histoire", "Un souvenir du jardin", "Faire vivre la mémoire collective.", "Choisir une photo marquante de l’année et noter en quelques phrases les personnes, le moment et ce qui a été appris. Ces récits nourrissent la vie du jardin."),
    ("atelier", "Cartes à planter", "Des vœux qui deviendront des fleurs.", "Mélanger des chutes de papier non glacé trempées et mixées avec quelques graines locales. Étaler, laisser sécher puis découper de petites cartes."),
    ("surprise", "Joyeux Noël du jardin", "L’image est maintenant entièrement révélée !", "Merci d’avoir ouvert les 24 cases avec nous. Que cette fin d’année soit douce, curieuse et pleine de projets à cultiver ensemble."),
]

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
    "home_about_eyebrow": "Association de quartier",
    "home_about_title": "Un site pour faire vivre le jardin entre deux permanences",
    "home_events_eyebrow": "Programmation",
    "home_events_title": "Les prochains rendez-vous",
    "home_events_link_label": "Tout voir",
    "home_events_empty": "Aucun rendez-vous à venir pour le moment.",
    "home_articles_eyebrow": "Carnet de bord",
    "home_articles_title": "Articles mis en avant",
    "home_articles_link_label": "Tous les articles",
    "home_articles_empty": "Les articles mis en avant apparaîtront ici.",
    "home_photos_eyebrow": "Galerie",
    "home_photos_title": "Images du jardin",
    "home_photos_link_label": "Ouvrir la galerie",
    "home_photos_empty_title": "La galerie est prête",
    "home_photos_empty_text": "Les premières photos ajoutées depuis l’administration apparaîtront ici.",
    "contact_email": "contact@vert-tige.local",
    "logo_url": "/static/logo-vert-tige-detoure.png",
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


def file_size_label(size: int) -> str:
    units = ["o", "Ko", "Mo", "Go"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "o":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{size} o"


def backup_path_from_name(filename: str) -> Path | None:
    if not BACKUP_NAME_RE.fullmatch(filename):
        return None
    path = (BACKUP_DIR / filename).resolve()
    if not str(path).startswith(str(BACKUP_DIR.resolve())):
        return None
    return path


def list_backup_files() -> list[Path]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        (path for path in BACKUP_DIR.glob("vert-tige-backup-*.zip") if BACKUP_NAME_RE.fullmatch(path.name)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def recent_log_lines(limit: int = 220) -> list[str]:
    if not LOG_PATH.exists():
        return []
    try:
        return LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []


def add_tree_to_zip(archive: zipfile.ZipFile, root: Path, archive_root: str) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file():
            archive.write(path, f"{archive_root}/{path.relative_to(root).as_posix()}")


def create_backup_archive() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = BACKUP_DIR / f"vert-tige-backup-{stamp}.zip"
    temp_archive_path = BACKUP_DIR / f".{archive_path.name}.tmp"
    temp_db_path = BACKUP_DIR / f".vert-tige-{stamp}.sqlite3"
    try:
        source = sqlite3.connect(DB_PATH)
        target = sqlite3.connect(temp_db_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        with zipfile.ZipFile(temp_archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_db_path, "data/vert_tige.sqlite3")
            add_tree_to_zip(archive, UPLOAD_DIR, "static/uploads")
            if LOG_PATH.exists():
                archive.write(LOG_PATH, "logs/server.log")
            for log_name in ["server.out.log", "server.err.log"]:
                log_path = BASE_DIR / log_name
                if log_path.exists():
                    archive.write(log_path, f"logs/{log_name}")
            archive.writestr(
                "README-sauvegarde.txt",
                "\n".join(
                    [
                        "Sauvegarde Vert-Tige",
                        f"Créée le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
                        "",
                        "Contenu :",
                        "- data/vert_tige.sqlite3 : base de données SQLite du site",
                        "- static/uploads/ : images envoyées depuis l'administration",
                        "- logs/ : journaux locaux du serveur",
                        "",
                        "Pour restaurer, arrêter le serveur, remplacer la base et recopier les fichiers uploads.",
                    ]
                ),
            )
        temp_archive_path.replace(archive_path)
        write_log(f"Sauvegarde créée : {archive_path.name}")
        return archive_path
    finally:
        for path in [temp_archive_path, temp_db_path]:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass


def insert_admin_activity(
    username: str,
    action: str,
    target: str = "",
    details: str = "",
    ip_address: str = "",
    user_id: int | None = None,
) -> None:
    message = " - ".join(part for part in [username, action, target, details] if part)
    write_log(f"Audit admin : {message}")
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_activity_logs
                    (user_id, username, action, target, details, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username[:120],
                    action[:180],
                    target[:180],
                    details[:500],
                    ip_address[:80],
                    now_iso(),
                ),
            )
    except sqlite3.Error as exc:
        write_log(f"Erreur journal admin : {exc}")


def admin_action_summary(path: str) -> tuple[str, str, str]:
    action = "Action d’administration"
    target = path
    details = ""
    if path == "/admin/home":
        return "Mise à jour de l’accueil", "Accueil", "Textes, images, footer, réseaux sociaux ou référencement"
    if path == "/admin/practical":
        return "Mise à jour des infos pratiques", "Infos pratiques", "Adresse, transports, carte ou horaires"
    if path == "/admin/events/save":
        return "Création d’un événement", "Programmation", ""
    if match := re.fullmatch(r"/admin/events/(\d+)/save", path):
        return "Modification d’un événement", f"Événement #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/events/(\d+)/delete", path):
        return "Suppression d’un événement", f"Événement #{match.group(1)}", ""
    if path == "/admin/articles/save":
        return "Création d’un article", "Articles", ""
    if match := re.fullmatch(r"/admin/articles/(\d+)/save", path):
        return "Modification d’un article", f"Article #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/articles/(\d+)/delete", path):
        return "Suppression d’un article", f"Article #{match.group(1)}", ""
    if path == "/admin/noel/create":
        return "Création d’une édition de Noël", "Calendrier de l’Avent", ""
    if match := re.fullmatch(r"/admin/noel/(\d+)/save", path):
        return "Modification d’une édition de Noël", f"Calendrier #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/noel/(\d+)/delete", path):
        return "Suppression d’une édition de Noël", f"Calendrier #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/noel/(\d+)/jours/(\d+)", path):
        return "Modification d’une case de l’Avent", f"Calendrier #{match.group(1)}, jour {match.group(2)}", ""
    if path == "/admin/photos/albums/create":
        return "Création d’un album photo", "Photos", ""
    if match := re.fullmatch(r"/admin/photos/albums/(\d+)/delete", path):
        return "Suppression d’un album photo", f"Album #{match.group(1)}", ""
    if path == "/admin/photos/upload":
        return "Ajout de photos", "Photos", ""
    if match := re.fullmatch(r"/admin/photos/(\d+)/visibility", path):
        return "Modification de visibilité photo", f"Photo #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/photos/(\d+)/delete", path):
        return "Suppression d’une photo", f"Photo #{match.group(1)}", ""
    if path == "/admin/messages/settings":
        return "Mise à jour de la messagerie", "Messages", "Adresse de contact ou paramètres du formulaire"
    if match := re.fullmatch(r"/admin/messages/(\d+)/toggle", path):
        return "Changement de statut d’un message", f"Message #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/messages/(\d+)/delete", path):
        return "Suppression d’un message traité", f"Message #{match.group(1)}", ""
    if path == "/admin/users/create":
        return "Création d’un compte administrateur", "Comptes", ""
    if match := re.fullmatch(r"/admin/users/(\d+)/save", path):
        return "Modification d’un compte administrateur", f"Compte #{match.group(1)}", ""
    if match := re.fullmatch(r"/admin/users/(\d+)/password", path):
        return "Changement de mot de passe administrateur", f"Compte #{match.group(1)}", "Mot de passe non journalisé"
    if path == "/admin/maintenance/backups/create":
        return "Création d’une sauvegarde", "Maintenance", ""
    if match := re.fullmatch(r"/admin/maintenance/backups/([^/]+)/delete", path):
        return "Suppression d’une sauvegarde", "Maintenance", unquote(match.group(1))
    return action, target, details


def admin_action_requires_owner(path: str) -> bool:
    return (
        path == "/admin/users/create"
        or bool(re.fullmatch(r"/admin/users/\d+/(save|password)", path))
        or path == "/admin/maintenance/backups/create"
        or bool(re.fullmatch(r"/admin/maintenance/backups/[^/]+/delete", path))
    )


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


TEXT_REPAIR_REPLACEMENTS = {
    "? partir": "À partir",
    " ? partir": " À partir",
    "� partir": "À partir",
    " � partir": " À partir",
    "v?rifier": "vérifier",
    "V?rifier": "Vérifier",
    "premi?re": "première",
    "Premi?re": "Première",
    "Deuxi?me": "Deuxième",
    "deuxi?me": "deuxième",
    "Troisi?me": "Troisième",
    "troisi?me": "troisième",
    "Troisi�me": "Troisième",
    "troisi�me": "troisième",
    "Quatri?me": "Quatrième",
    "quatri?me": "quatrième",
    "Quatri�me": "Quatrième",
    "quatri�me": "quatrième",
    "pr?paration": "préparation",
    "Pr?paration": "Préparation",
    "compl?ter": "compléter",
    "Compl?ter": "Compléter",
    "rang?e": "rangée",
    "Rang?e": "Rangée",
    "rang�e": "rangée",
    "Rang�e": "Rangée",
    "contr?ler": "contrôler",
    "Contr?ler": "Contrôler",
    "contr�ler": "contrôler",
    "Contr�ler": "Contrôler",
    "hi?rarchie": "hiérarchie",
    "Hi?rarchie": "Hiérarchie",
    "hi�rarchie": "hiérarchie",
    "Hi�rarchie": "Hiérarchie",
    "r?colte": "récolte",
    "R?colte": "Récolte",
    "r�colte": "récolte",
    "R�colte": "Récolte",
    "partag?e": "partagée",
    "Partag?e": "Partagée",
    "partag�e": "partagée",
    "Partag�e": "Partagée",
    " ? tester": " à tester",
    " � tester": " à tester",
    "l?affichage": "l’affichage",
    "L?affichage": "L’affichage",
    "l?administration": "l’administration",
    "L?administration": "L’administration",
    "l?association": "l’association",
    "L?association": "L’association",
    "l?accueil": "l’accueil",
    "L?accueil": "L’accueil",
    "d?accueil": "d’accueil",
    "D?accueil": "D’accueil",
    "d?administration": "d’administration",
    "D?administration": "D’administration",
    "d?une": "d’une",
    "D?une": "D’une",
    "d?un": "d’un",
    "D?un": "D’un",
    "peut ?tre": "peut être",
    "doit ?tre": "doit être",
    "?tre": "être",
    "�tre": "être",
    "?tait": "était",
    "supprim?e": "supprimée",
    "supprim?": "supprimé",
    "termin?e": "terminée",
    "termin?": "terminé",
    "termin�e": "terminée",
    "termin�": "terminé",
    "valid?e": "validée",
    "valid?": "validé",
    "cr?er": "créer",
    "Cr?er": "Créer",
    "cr?ation": "création",
    "Cr?ation": "Création",
    "cat?gorie": "catégorie",
    "Cat?gorie": "Catégorie",
    "cat?gories": "catégories",
    "Cat?gories": "Catégories",
    "r?f?rencement": "référencement",
    "R?f?rencement": "Référencement",
    "g?n?ral": "général",
    "G?n?ral": "Général",
    "d?j?": "déjà",
    "D?j?": "Déjà",
    "tr?s": "très",
    "Tr?s": "Très",
    "apr?s": "après",
    "Apr?s": "Après",
    "o? se": "où se",
    "O? se": "Où se",
}


def repair_text_encoding(value: str | None) -> str | None:
    if value is None:
        return None
    repaired = value
    if "Ã" in repaired or "Â" in repaired or "�" in repaired:
        try:
            candidate = repaired.encode("latin1").decode("utf-8")
        except UnicodeError:
            candidate = repaired
        if candidate.count("�") <= repaired.count("�"):
            repaired = candidate
        repaired = repaired.replace("\u00a0", " ")
    for broken, fixed in TEXT_REPAIR_REPLACEMENTS.items():
        repaired = repaired.replace(broken, fixed)
    return repaired


def repair_stored_text_encoding(conn: sqlite3.Connection) -> None:
    for table in [
        "settings",
        "events",
        "articles",
        "photos",
        "photo_albums",
        "messages",
        "admin_users",
        "admin_activity_logs",
        "christmas_calendars",
        "christmas_days",
    ]:
        columns = [
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})")
            if row["type"].upper().startswith("TEXT")
        ]
        if not columns:
            continue
        rows = conn.execute(
            f"SELECT rowid AS _rowid, {', '.join(columns)} FROM {table}"
        ).fetchall()
        for row in rows:
            updates = {
                column: repair_text_encoding(row[column])
                for column in columns
                if repair_text_encoding(row[column]) != row[column]
            }
            if not updates:
                continue
            assignments = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(
                f"UPDATE {table} SET {assignments} WHERE rowid = ?",
                (*updates.values(), row["_rowid"]),
            )


def format_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = date.fromisoformat(value)
        return f"{parsed.day} {MONTHS[parsed.month]} {parsed.year}"
    except ValueError:
        return e(value)


def format_datetime(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d/%m/%Y %H:%M")
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


def normalize_christmas_category(value: str | None) -> str:
    candidate = (value or "surprise").strip()
    return candidate if candidate in CHRISTMAS_CATEGORY_LABELS else "surprise"


def christmas_category_options(selected: str | None = "surprise") -> str:
    current = normalize_christmas_category(selected)
    return "".join(
        f'<option value="{key}" {"selected" if key == current else ""}>{e(label)}</option>'
        for key, label in CHRISTMAS_CATEGORY_LABELS.items()
    )


def normalize_hex_color(value: str | None) -> str:
    candidate = (value or "").strip()
    return candidate.lower() if re.fullmatch(r"#[0-9a-fA-F]{6}", candidate) else CHRISTMAS_ACCENT_DEFAULT


def christmas_day_is_open(year: int, day_number: int, today: date, enabled: bool = True) -> bool:
    if not enabled or day_number < 1 or day_number > 24:
        return False
    if today.year > year:
        return True
    if today.year < year or today.month != 12:
        return False
    return today.day >= 25 or today.day == day_number


def christmas_day_can_restore(
    year: int, day_number: int, today: date, enabled: bool = True
) -> bool:
    """A past case may only reopen before Christmas when its cookie says it was seen."""
    if not enabled or day_number < 1 or day_number > 24:
        return False
    return (
        today.year == year
        and today.month == 12
        and today.day < 25
        and day_number < today.day
    )


def normalize_christmas_layout_variant(value: object) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return 1
    return candidate if 1 <= candidate <= 12 else 1


def christmas_layout_options(selected: object = 1) -> str:
    current = normalize_christmas_layout_variant(selected)
    return "".join(
        f'<option value="{variant}" {"selected" if variant == current else ""}>Puzzle {variant}</option>'
        for variant in range(1, 13)
    )


def christmas_door_positions(year: int, variant: object = 1) -> list[int]:
    """Return one stable, shuffled visual grid position for each day 1..24."""
    layout_variant = normalize_christmas_layout_variant(variant)
    positions = list(range(1, 25))
    positions.sort(
        key=lambda position: hashlib.sha256(
            f"vert-tige-noel:{year}:{layout_variant}:{position}".encode("utf-8")
        ).digest()
    )
    return positions


def christmas_puzzle_tabs(year: int, variant: object, row: int, column: int) -> list[str]:
    seed = year + normalize_christmas_layout_variant(variant) * 17
    tabs: list[str] = []
    if column < 6 and (seed + row + column) % 2 == 0:
        tabs.append("right")
    if column > 1 and (seed + row + column - 1) % 2 != 0:
        tabs.append("left")
    if row < 4 and (seed + row + column) % 2 == 0:
        tabs.append("bottom")
    if row > 1 and (seed + row - 1 + column) % 2 != 0:
        tabs.append("top")
    return tabs


def christmas_puzzle_path_data(year: int, variant: object) -> tuple[str, str]:
    """Build one continuous 6x4 jigsaw guide in a 600x400 coordinate space."""
    layout_variant = normalize_christmas_layout_variant(variant)
    seed = year + layout_variant * 17
    vertical: list[str] = []
    horizontal: list[str] = []
    for column in range(1, 6):
        x = column * 100
        for row in range(1, 5):
            y = (row - 1) * 100
            direction = 1 if (seed + row + column) % 2 == 0 else -1
            bulge = direction * 28
            vertical.append(
                f"M{x} {y}V{y + 34}C{x + bulge} {y + 34} "
                f"{x + bulge} {y + 66} {x} {y + 66}V{y + 100}"
            )
    for row in range(1, 4):
        y = row * 100
        for column in range(1, 7):
            x = (column - 1) * 100
            direction = 1 if (seed + row + column) % 2 == 0 else -1
            bulge = direction * 28
            horizontal.append(
                f"M{x} {y}H{x + 34}C{x + 34} {y + bulge} "
                f"{x + 66} {y + bulge} {x + 66} {y}H{x + 100}"
            )
    return "".join(vertical), "".join(horizontal)


def christmas_puzzle_overlay_svg(year: int, variant: object, admin: bool = False) -> str:
    vertical, horizontal = christmas_puzzle_path_data(year, variant)
    css_class = "christmas-cut-overlay" if admin else "christmas-puzzle-outline"
    data_attributes = (
        ' data-christmas-cut-overlay data-christmas-cut-vertical data-christmas-cut-horizontal'
        if admin
        else ""
    )
    return f"""
    <svg class="{css_class}" viewBox="0 0 600 400" preserveAspectRatio="none" aria-hidden="true"{data_attributes}>
      <rect class="christmas-puzzle-border" x="1.5" y="1.5" width="597" height="397" rx="3"></rect>
      <path class="christmas-puzzle-lines christmas-puzzle-lines-vertical" data-puzzle-vertical d="{vertical}"></path>
      <path class="christmas-puzzle-lines christmas-puzzle-lines-horizontal" data-puzzle-horizontal d="{horizontal}"></path>
    </svg>
    """


def christmas_piece_clip_path_data(year: int, variant: object, position: int) -> str:
    """Return a board-relative path for one interlocking puzzle piece."""
    row = (position - 1) // 6 + 1
    column = (position - 1) % 6 + 1
    x0 = (column - 1) / 6
    y0 = (row - 1) / 4
    width = 1 / 6
    height = 1 / 4
    x1 = x0 + width
    y1 = y0 + height
    x34 = x0 + width * 0.34
    x66 = x0 + width * 0.66
    y34 = y0 + height * 0.34
    y66 = y0 + height * 0.66
    tabs = set(christmas_puzzle_tabs(year, variant, row, column))

    def n(value: float) -> str:
        return f"{value:.6f}".rstrip("0").rstrip(".")

    parts = [f"M{n(x0)} {n(y0)}"]
    if row == 1:
        parts.append(f"H{n(x1)}")
    else:
        top_bulge = -height * 0.28 if "top" in tabs else height * 0.28
        parts.append(
            f"H{n(x34)}C{n(x34)} {n(y0 + top_bulge)} "
            f"{n(x66)} {n(y0 + top_bulge)} {n(x66)} {n(y0)}H{n(x1)}"
        )
    if column == 6:
        parts.append(f"V{n(y1)}")
    else:
        right_bulge = width * 0.28 if "right" in tabs else -width * 0.28
        parts.append(
            f"V{n(y34)}C{n(x1 + right_bulge)} {n(y34)} "
            f"{n(x1 + right_bulge)} {n(y66)} {n(x1)} {n(y66)}V{n(y1)}"
        )
    if row == 4:
        parts.append(f"H{n(x0)}")
    else:
        bottom_bulge = height * 0.28 if "bottom" in tabs else -height * 0.28
        parts.append(
            f"H{n(x66)}C{n(x66)} {n(y1 + bottom_bulge)} "
            f"{n(x34)} {n(y1 + bottom_bulge)} {n(x34)} {n(y1)}H{n(x0)}"
        )
    if column == 1:
        parts.append(f"V{n(y0)}")
    else:
        left_bulge = -width * 0.28 if "left" in tabs else width * 0.28
        parts.append(
            f"V{n(y66)}C{n(x0 + left_bulge)} {n(y66)} "
            f"{n(x0 + left_bulge)} {n(y34)} {n(x0)} {n(y34)}V{n(y0)}"
        )
    parts.append("Z")
    return "".join(parts)


def christmas_puzzle_clip_definitions(year: int, variant: object) -> str:
    clips = "".join(
        f'<clipPath id="christmas-piece-{position}" clipPathUnits="objectBoundingBox">'
        f'<path d="{christmas_piece_clip_path_data(year, variant, position)}"></path>'
        f"</clipPath>"
        for position in range(1, 25)
    )
    return f'<svg class="christmas-piece-definitions" width="0" height="0" aria-hidden="true"><defs>{clips}</defs></svg>'


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


def christmas_public_window(today: date | None = None) -> bool:
    return (today or date.today()).month == 12


def christmas_nav_enabled(today: date | None = None) -> bool:
    display_date = today or date.today()
    if not christmas_public_window(display_date):
        return False
    try:
        with connect() as conn:
            calendar = conn.execute(
                "SELECT show_in_nav FROM christmas_calendars WHERE year = ? AND published = 1",
                (display_date.year,),
            ).fetchone()
            if calendar is None:
                calendar = conn.execute(
                    "SELECT show_in_nav FROM christmas_calendars WHERE published = 1 ORDER BY year DESC LIMIT 1"
                ).fetchone()
            return bool(calendar and calendar["show_in_nav"])
    except sqlite3.Error:
        return False


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


def content_search_score(title: str, body: str, tokens: list[str], phrase: str) -> int:
    if not tokens:
        return 0
    normalized_title = normalize_search_text(title)
    normalized_body = normalize_search_text(body)
    score = 0
    if phrase and phrase in normalized_title:
        score += 90
    elif phrase and phrase in normalized_body:
        score += 35
    for token in tokens:
        if token in normalized_title:
            score += 45
            if normalized_title.startswith(token):
                score += 12
        if token in normalized_body:
            score += 14
    return score


def site_search_results(query: str) -> list[dict[str, str | int]]:
    tokens = search_tokens(query)
    if not tokens:
        return []
    phrase = normalize_search_text(query)
    settings = read_settings()
    results: list[dict[str, str | int]] = []

    def add_result(kind: str, title: str, summary: str, url: str, date_value: str = "") -> None:
        score = content_search_score(title, summary, tokens, phrase)
        if score <= 0:
            return
        results.append(
            {
                "kind": kind,
                "title": title,
                "summary": compact_text(summary, title, 220),
                "url": url,
                "date": date_value,
                "score": score,
            }
        )

    with connect() as conn:
        articles = conn.execute(
            "SELECT * FROM articles WHERE published = 1 ORDER BY created_at DESC"
        ).fetchall()
        events = conn.execute(
            "SELECT * FROM events ORDER BY starts_on DESC, start_time DESC"
        ).fetchall()
        photos = conn.execute(
            """
            SELECT p.*, a.slug AS album_slug, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            WHERE p.visibility IN ('gallery', 'both')
            ORDER BY p.created_at DESC
            """
        ).fetchall()

    for row in articles:
        add_result(
            "Article",
            row["title"],
            " ".join([row["summary"] or "", row["body"] or ""]),
            f"/articles/{quote(row['slug'])}",
            row["created_at"][:10],
        )
    for row in events:
        add_result(
            "Programmation",
            row["title"],
            " ".join(
                [
                    event_schedule(row),
                    event_place(row),
                    row["description"] or "",
                ]
            ),
            f"/agenda#event-{row['id']}",
            row["starts_on"],
        )
    for row in photos:
        album_path = f"?album={quote(row['album_slug'])}" if row["album_slug"] else ""
        add_result(
            "Galerie",
            row["title"] or "Photo du jardin",
            " ".join([row["caption"] or "", row["album_name"] or ""]),
            f"/galerie{album_path}",
            row["created_at"][:10],
        )

    add_result(
        "Page",
        "Accueil",
        " ".join(
            [
                settings.get("home_intro", ""),
                settings.get("home_about_title", ""),
                settings.get("home_about_text", ""),
            ]
        ),
        "/",
    )
    add_result(
        "Page",
        "Infos pratiques",
        " ".join(
            [
                settings.get("practical_title", ""),
                settings.get("practical_intro", ""),
                settings.get("practical_address", ""),
                settings.get("practical_bus", ""),
                settings.get("practical_metro", ""),
                settings.get("practical_tram", ""),
                settings.get("practical_opening", ""),
            ]
        ),
        "/infos-pratiques",
    )
    add_result("Page", "Contact", settings.get("contact_email", ""), "/contact")
    add_result(
        "Page",
        "Mentions légales",
        " ".join([settings.get("legal_publisher", ""), settings.get("legal_text", "")]),
        "/mentions-legales",
    )

    results.sort(key=lambda item: (int(item["score"]), str(item["date"])), reverse=True)
    return results


def search_result_card(result: dict[str, str | int]) -> str:
    date_html = (
        f'<span>{format_date(str(result["date"]))}</span>'
        if result.get("date")
        else ""
    )
    return f"""
    <article class="search-result-card">
      <p class="meta"><strong>{e(str(result["kind"]))}</strong>{date_html}</p>
      <h3><a href="{e(str(result["url"]))}">{e(str(result["title"]))}</a></h3>
      <p>{e(str(result["summary"]))}</p>
    </article>
    """


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


def make_captcha_challenge() -> tuple[str, str]:
    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 2
    issued_at = int(time.time())
    payload = f"{left + right}:{issued_at}:{secrets.token_hex(6)}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(SESSION_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"Combien font {left} + {right} ?", f"{encoded}.{signature}"


def verify_captcha_answer(answer: str | None, token: str | None) -> bool:
    if not answer or not token:
        return False
    try:
        encoded, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(SESSION_SECRET.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not secrets.compare_digest(signature, expected):
        return False
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        expected_answer, issued_at, _nonce = decoded.split(":", 2)
        issued = int(issued_at)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return False
    if time.time() - issued > 30 * 60:
        return False
    return answer.strip() == expected_answer


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
    contact_email = settings.get("contact_email", "").strip()
    if valid_email(contact_email) and not contact_email.lower().endswith(".local"):
        schema["email"] = contact_email
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
            "target": absolute_url("/recherche?q={search_term_string}", settings),
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
    if row["image_url"]:
        schema["image"] = absolute_url(row["image_url"], settings)
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


def populate_christmas_days(
    conn: sqlite3.Connection,
    calendar_id: int,
    source_calendar_id: int | None = None,
) -> None:
    created = now_iso()
    if source_calendar_id is not None:
        source_rows = conn.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = ? ORDER BY day_number",
            (source_calendar_id,),
        ).fetchall()
        for row in source_rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO christmas_days
                    (calendar_id, day_number, category, title, teaser, body, image_url,
                     link_url, link_label, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    calendar_id,
                    row["day_number"],
                    row["category"],
                    row["title"],
                    row["teaser"],
                    row["body"],
                    row["image_url"],
                    row["link_url"],
                    row["link_label"],
                    row["enabled"],
                    created,
                ),
            )
    for day_number, (category, title, teaser, body) in enumerate(DEFAULT_CHRISTMAS_DAYS, 1):
        conn.execute(
            """
            INSERT OR IGNORE INTO christmas_days
                (calendar_id, day_number, category, title, teaser, body, image_url,
                 link_url, link_label, enabled, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, '', '', '', 1, ?)
            """,
            (calendar_id, day_number, category, title, teaser, body, created),
        )


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
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
                image_url TEXT,
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

            CREATE TABLE IF NOT EXISTS admin_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS christmas_calendars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL UNIQUE,
                eyebrow TEXT,
                title TEXT NOT NULL,
                intro TEXT,
                image_url TEXT,
                accent_color TEXT NOT NULL DEFAULT '#a62f2f',
                layout_variant INTEGER NOT NULL DEFAULT 1,
                completion_enabled INTEGER NOT NULL DEFAULT 1,
                completion_title TEXT NOT NULL DEFAULT 'Bravo, vous avez complété le calendrier !',
                completion_message TEXT NOT NULL DEFAULT 'Vous avez découvert les 24 surprises du jardin. Toute l’équipe de l’association vous souhaite de très belles fêtes !',
                completion_link_label TEXT NOT NULL DEFAULT 'Découvrir la surprise',
                completion_link_url TEXT,
                published INTEGER NOT NULL DEFAULT 0,
                show_in_nav INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS christmas_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calendar_id INTEGER NOT NULL,
                day_number INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'surprise',
                title TEXT NOT NULL,
                teaser TEXT,
                body TEXT,
                image_url TEXT,
                link_url TEXT,
                link_label TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                UNIQUE(calendar_id, day_number)
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
                "image_url": "TEXT",
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
        ensure_columns(
            conn,
            "christmas_calendars",
            {
                "layout_variant": "INTEGER NOT NULL DEFAULT 1",
                "completion_enabled": "INTEGER NOT NULL DEFAULT 1",
                "completion_title": "TEXT NOT NULL DEFAULT 'Bravo, vous avez complété le calendrier !'",
                "completion_message": "TEXT NOT NULL DEFAULT 'Vous avez découvert les 24 surprises du jardin. Toute l’équipe de l’association vous souhaite de très belles fêtes !'",
                "completion_link_label": "TEXT NOT NULL DEFAULT 'Découvrir la surprise'",
                "completion_link_url": "TEXT",
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
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'home_events_eyebrow' AND value = ?",
            ("Programmation", "Prochains rendez-vous"),
        )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'home_events_title' AND value = ?",
            ("Les prochains rendez-vous", "Agenda du jardin"),
        )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'logo_url' AND COALESCE(value, '') = ''",
            (DEFAULT_SETTINGS["logo_url"],),
        )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'logo_url' AND value = ?",
            (DEFAULT_SETTINGS["logo_url"], "/static/logo-vert-tige.png"),
        )
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = 'home_photos_eyebrow' AND value = ?",
            ("Galerie", "Banque de photos"),
        )
        repair_stored_text_encoding(conn)
        conn.execute(
            "UPDATE christmas_calendars SET image_url = ? WHERE image_url = ?",
            (CHRISTMAS_DEFAULT_IMAGE, "/static/hero-garden.png"),
        )

        christmas_count = conn.execute(
            "SELECT COUNT(*) AS count FROM christmas_calendars"
        ).fetchone()["count"]
        if christmas_count == 0:
            created = now_iso()
            cursor = conn.execute(
                """
                INSERT INTO christmas_calendars
                    (year, eyebrow, title, intro, image_url, accent_color, layout_variant,
                     published, show_in_nav, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 3, 1, 1, ?, ?)
                """,
                (
                    2026,
                    "24 jours de découvertes",
                    "Le calendrier de l’Avent du jardin",
                    "Chaque jour, une nouvelle partie de l’image se dévoile avec une recette, un conseil jardinage ou une idée à partager.",
                    CHRISTMAS_DEFAULT_IMAGE,
                    CHRISTMAS_ACCENT_DEFAULT,
                    created,
                    created,
                ),
            )
            populate_christmas_days(conn, cursor.lastrowid)
        else:
            for calendar in conn.execute("SELECT id FROM christmas_calendars").fetchall():
                populate_christmas_days(conn, calendar["id"])

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
                    (title, starts_on, ends_on, start_time, end_time, location, address, image_url, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        "",
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
                        "",
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
      <p>Avec ton accord, le calendrier de l’Avent mémorise les cases découvertes dans un cookie sur cet appareil. Si les cookies sont supprimés, cette progression sera perdue. Les statistiques, la publicité et les contenus externes restent eux aussi soumis à ton choix.</p>
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
    cookie_controls_enabled: bool = True,
) -> str:
    settings = read_settings()
    site_title = settings["site_title"]
    logo_url = settings.get("logo_url", "")
    stylesheet_url = versioned_static_url("/static/styles.css")
    editor_url = versioned_static_url("/static/article-editor.js")
    privacy_url = versioned_static_url("/static/privacy.js")
    favicon_ico_url = versioned_static_url("/static/favicon.ico")
    favicon_png_url = versioned_static_url("/static/favicon-32.png")
    apple_touch_icon_url = versioned_static_url("/static/apple-touch-icon.png")
    facebook_path = "M22 12.06C22 6.49 17.52 2 11.94 2S2 6.49 2 12.06c0 5.02 3.66 9.19 8.44 9.94v-7.03H7.9v-2.91h2.54V9.85c0-2.51 1.49-3.9 3.77-3.9 1.09 0 2.23.2 2.23.2v2.46h-1.25c-1.24 0-1.63.77-1.63 1.56v1.89h2.78l-.44 2.91h-2.34V22c4.78-.75 8.44-4.92 8.44-9.94z"
    instagram_path = "M7.7 2h8.6A5.7 5.7 0 0 1 22 7.7v8.6a5.7 5.7 0 0 1-5.7 5.7H7.7A5.7 5.7 0 0 1 2 16.3V7.7A5.7 5.7 0 0 1 7.7 2zm0 2A3.7 3.7 0 0 0 4 7.7v8.6A3.7 3.7 0 0 0 7.7 20h8.6a3.7 3.7 0 0 0 3.7-3.7V7.7A3.7 3.7 0 0 0 16.3 4H7.7zm4.3 3.35A4.65 4.65 0 1 1 7.35 12 4.65 4.65 0 0 1 12 7.35zm0 2A2.65 2.65 0 1 0 14.65 12 2.65 2.65 0 0 0 12 9.35zm5.03-2.2a1.08 1.08 0 1 1-1.08 1.08 1.08 1.08 0 0 1 1.08-1.08z"
    gear_path = "M19.43 12.98c.04-.32.07-.65.07-.98s-.02-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1a7.28 7.28 0 0 0-1.69-.98L14.5 2.42A.5.5 0 0 0 14 2h-4a.5.5 0 0 0-.5.42L9.12 5.07c-.6.24-1.16.56-1.69.98l-2.49-1a.5.5 0 0 0-.61.22l-2 3.46c-.12.22-.07.49.12.64l2.11 1.65c-.04.32-.06.65-.06.98s.02.66.06.98l-2.11 1.65a.5.5 0 0 0-.12.64l2 3.46c.13.22.39.31.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.38-2.65c.6-.25 1.17-.58 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46a.5.5 0 0 0-.12-.64l-2.12-1.65zM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5z"
    search_path = "M10.5 4a6.5 6.5 0 0 1 5.17 10.44l4.45 4.44-1.42 1.42-4.44-4.45A6.5 6.5 0 1 1 10.5 4zm0 2a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z"
    is_admin_area = current_path.startswith("/admin")
    social_links = (
        social_icon_link(settings.get("facebook_url", ""), "Facebook", facebook_path, "facebook")
        + social_icon_link(settings.get("instagram_url", ""), "Instagram", instagram_path, "instagram")
    )
    show_instagram_banner = current_path == "/" or current_path.startswith("/galerie")
    instagram_banner = instagram_footer_banner(settings) if show_instagram_banner else ""
    privacy_ui_enabled = cookie_controls_enabled and not current_path.startswith("/admin")
    cookie_controls = cookie_consent_html() if privacy_ui_enabled else ""
    cookie_footer_button = (
        ""
        if not privacy_ui_enabled
        else '<button class="footer-cookie-link" type="button" data-cookie-open>Gestion des cookies</button>'
    )
    tracking_head = google_ads_head(settings, track_conversion) if privacy_ui_enabled else ""
    brand_mark = (
        f'<img class="brand-logo" src="{e(logo_url)}" alt="">'
        if logo_url
        else '<span class="brand-mark">VT</span>'
    )
    brand_class = "brand has-logo" if logo_url else "brand"
    header_class = "site-header admin-site-header" if is_admin_area else "site-header"
    header_search = (
        ""
        if is_admin_area
        else f"""
    <form class="header-search" method="get" action="/recherche" role="search" aria-label="Rechercher sur le site">
      <label class="visually-hidden" for="header-site-search">Rechercher sur le site</label>
      <input id="header-site-search" type="search" name="q" placeholder="Rechercher sur le site" autocomplete="off">
      <button type="submit" aria-label="Lancer la recherche">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="{search_path}"></path></svg>
      </button>
    </form>"""
    )
    nav_items = [
        nav_link("/", "Accueil", current_path),
        nav_link("/agenda", "Programmation", current_path),
        nav_link("/articles", "Articles", current_path),
        nav_link("/galerie", "Photos", current_path),
    ]
    if christmas_nav_enabled():
        nav_items.append(nav_link("/noel", "Noël", current_path))
    nav_items.extend(
        [
            nav_link("/infos-pratiques", "Infos pratiques", current_path),
            nav_link("/contact", "Contact", current_path),
        ]
    )
    nav = "".join(nav_items)
    footer_class = "site-footer footer-reveal"
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(page_title(title, settings))}</title>
  {seo_head(settings, title, current_path, description, image_url, og_type, structured_data, indexable)}
  <link rel="icon" href="{e(favicon_ico_url)}" sizes="any">
  <link rel="icon" type="image/png" href="{e(favicon_png_url)}" sizes="32x32">
  <link rel="apple-touch-icon" href="{e(apple_touch_icon_url)}">
  <link rel="stylesheet" href="{e(stylesheet_url)}">
  <script src="{e(editor_url)}" defer></script>
  <script src="{e(privacy_url)}" defer></script>
  {tracking_head}
</head>
<body>
  <header class="{header_class}">
    <button class="mobile-menu-toggle" type="button" aria-label="Ouvrir le menu" aria-controls="main-nav" aria-expanded="false" data-mobile-menu-toggle>
      <span></span><span></span><span></span>
    </button>
    <a class="{brand_class}" href="/" aria-label="{e(site_title)}">
      {brand_mark}
      <span class="brand-text"><strong>{e(site_title)}</strong><small>{e(settings["tagline"])}</small></span>
    </a>
    {header_search}
    <nav class="main-nav" id="main-nav" aria-label="Navigation principale" data-main-nav>{nav}</nav>
  </header>
  <main>{body}</main>
  {instagram_banner}
  <footer class="{footer_class}">
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


def event_card(row: sqlite3.Row, modal: bool = False) -> str:
    image_html = (
        f'<img class="event-card-image" src="{e(row["image_url"])}" alt="">'
        if row["image_url"]
        else ""
    )
    modal_id = f"event-modal-{row['id']}"
    modal_attrs = (
        f' role="button" tabindex="0" data-event-modal-open="{modal_id}" '
        f'aria-haspopup="dialog" aria-controls="{modal_id}"'
        if modal
        else ""
    )
    cta_html = '<p class="event-card-cta">Voir le détail</p>' if modal else ""
    return f"""
    <article class="card event-card" id="event-{row['id']}"{modal_attrs}>
      <div class="date-badge"><strong>{date.fromisoformat(row["starts_on"]).day}</strong><span>{MONTHS[date.fromisoformat(row["starts_on"]).month][:3]}</span></div>
      <div>
        <p class="meta">{event_schedule(row)}</p>
        <h3>{e(row["title"])}</h3>
        <p class="place">{e(event_place(row))}</p>
        {image_html}
        {paragraphs(row["description"])}
        {cta_html}
      </div>
    </article>"""


def event_modal(row: sqlite3.Row) -> str:
    modal_id = f"event-modal-{row['id']}"
    image_html = (
        f'<img class="event-modal-image" src="{e(row["image_url"])}" alt="">'
        if row["image_url"]
        else ""
    )
    description_html = paragraphs(row["description"]) or "<p>Les détails de ce rendez-vous seront complétés prochainement.</p>"
    return f"""
    <div class="event-modal" id="{modal_id}" role="dialog" aria-modal="true" aria-labelledby="{modal_id}-title" data-event-modal hidden>
      <div class="event-modal-backdrop" data-event-modal-close></div>
      <article class="event-modal-panel" tabindex="-1">
        <button class="event-modal-close" type="button" aria-label="Fermer la fenêtre" data-event-modal-close>&times;</button>
        {image_html}
        <div class="event-modal-content">
          <p class="eyebrow">Rendez-vous</p>
          <h2 id="{modal_id}-title">{e(row["title"])}</h2>
          <dl class="event-modal-details">
            <div><dt>Date et horaire</dt><dd>{e(event_schedule(row))}</dd></div>
            <div><dt>Lieu</dt><dd>{e(event_place(row))}</dd></div>
          </dl>
          <div class="event-modal-description">{description_html}</div>
        </div>
      </article>
    </div>
    """


def event_modals(rows: list[sqlite3.Row]) -> str:
    return "".join(event_modal(row) for row in rows)


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
    event_html = "".join(event_card(row, modal=True) for row in events) or empty_state(settings["home_events_empty"])
    event_modal_html = event_modals(events)
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
      {event_modal_html}
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


def agenda_page(query: dict[str, list[str]]) -> str:
    settings = read_settings()
    today = date.today().isoformat()
    with connect() as conn:
        program = conn.execute(
            """
            SELECT * FROM events
            WHERE starts_on >= ?
            ORDER BY starts_on ASC, start_time ASC, created_at DESC
            LIMIT 20
            """,
            (today,),
        ).fetchall()

    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Programmation</p>
      <h1>Programmation</h1>
      <p>Les ateliers, permanences et moments collectifs de Vert-Tige.</p>
    </section>
    <section class="section">
      <div class="program-list">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Prochains rendez-vous</p>
            <h2>À venir</h2>
          </div>
        </div>
        <div class="list-stack">{"".join(event_card(row, modal=True) for row in program) or empty_state("Aucun rendez-vous à venir pour le moment.")}</div>
      </div>
      {event_modals(program)}
    </section>
    """
    return layout(
        "Programmation",
        body,
        "/agenda",
        description="Programmation des ateliers, permanences et événements du jardin partagé Vert-Tige à Paris 14.",
        image_url=settings.get("seo_image_url"),
        structured_data=[event_schema(row, settings) for row in program],
    )


def search_page(query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    search_query = query.get("q", [""])[0].strip()
    results = site_search_results(search_query) if search_query else []
    result_count = len(results)
    result_label = "résultat trouvé" if result_count == 1 else "résultats trouvés"
    clear_link = '<a class="button secondary" href="/recherche">Effacer</a>' if search_query else ""
    summary = (
        f'<p class="search-summary">{result_count} {result_label} pour <strong>{e(search_query)}</strong>.</p>'
        if search_query
        else '<p class="search-summary">Recherche dans les articles, la programmation, la galerie et les pages du site.</p>'
    )
    empty = (
        empty_state(f"Aucun résultat ne correspond à « {search_query} ».")
        if search_query and not results
        else ""
    )
    body = f"""
    <section class="page-hero compact-hero">
      <p class="eyebrow">Recherche</p>
      <h1>Rechercher sur le site</h1>
      <p>Retrouver une actualité, un rendez-vous, une photo ou une information pratique.</p>
    </section>
    <section class="section">
      <form class="article-search site-search" method="get" action="/recherche" role="search" aria-label="Rechercher sur le site">
        <label for="site-search">Recherche globale</label>
        <div class="search-row">
          <input id="site-search" type="search" name="q" value="{e(search_query)}" placeholder="Vide-greniers, compost, horaires..." autocomplete="off">
          <button class="button primary" type="submit">Rechercher</button>
          {clear_link}
        </div>
      </form>
      {summary}
      <div class="search-results">{"".join(search_result_card(result) for result in results) or empty}</div>
    </section>
    """
    return layout(
        "Recherche",
        body,
        "/recherche",
        description="Recherche globale sur le site Vert-Tige.",
        indexable=False,
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


def article_page(slug: str) -> str | None:
    settings = read_settings()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM articles WHERE slug = ? AND published = 1",
            (slug,),
        ).fetchone()
    if not row:
        return None
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
            HAVING COUNT(p.id) > 0
            ORDER BY a.name
            """
        ).fetchall()
        current_album = None
        params: tuple[object, ...] = ()
        where = "WHERE p.visibility IN ('gallery', 'both')"
        if album_slug:
            current_album = next((album for album in albums if album["slug"] == album_slug), None)
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
      <h1>{e(current_album['name']) if current_album else 'Galerie'}</h1>
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


def contact_page(sent: bool = False, saved: bool = False, error: str = "") -> str:
    settings = read_settings()
    captcha_question, captcha_token = make_captcha_challenge()
    if sent or saved:
        success = '<div class="notice success">Message bien reçu. L’équipe Vert-Tige pourra le consulter dans l’administration.</div>'
    elif error == "captcha":
        success = '<div class="notice error">La vérification anti-spam est incorrecte. Merci de réessayer.</div>'
    elif error == "validation":
        success = '<div class="notice error">Merci de renseigner un nom, un email valide et un message.</div>'
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
          <label class="captcha-field">{e(captcha_question)}<input required name="captcha_answer" inputmode="numeric" pattern="[0-9]*" autocomplete="off"></label>
          <input type="hidden" name="captcha_token" value="{e(captcha_token)}">
          <label class="honeypot-field">Site web<input name="website" tabindex="-1" autocomplete="off"></label>
          <button class="button primary" type="submit">Envoyer</button>
        </form>
      </div>
      <aside class="info-panel">
        <p class="eyebrow">Adresse de contact</p>
        <h3>{e(settings["contact_email"])}</h3>
        <p>Les messages envoyés depuis ce formulaire sont transmis à l’espace d’administration du site.</p>
      </aside>
    </section>
    """
    return layout(
        "Contact",
        body,
        "/contact",
        track_conversion=sent or saved,
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


def christmas_calendar_page(
    requested_year: int | None = None,
    today: date | None = None,
    preview_calendar_id: int | None = None,
    preview_unlock_all: bool = False,
) -> str | None:
    display_date = today or date.today()
    is_preview = preview_calendar_id is not None
    if not is_preview and not christmas_public_window(display_date):
        return None
    with connect() as conn:
        if preview_calendar_id is not None:
            calendar = conn.execute(
                "SELECT * FROM christmas_calendars WHERE id = ?",
                (preview_calendar_id,),
            ).fetchone()
        elif requested_year is not None:
            calendar = conn.execute(
                "SELECT * FROM christmas_calendars WHERE year = ? AND published = 1",
                (requested_year,),
            ).fetchone()
        else:
            calendar = conn.execute(
                "SELECT * FROM christmas_calendars WHERE year = ? AND published = 1",
                (display_date.year,),
            ).fetchone()
            if calendar is None:
                calendar = conn.execute(
                    "SELECT * FROM christmas_calendars WHERE published = 1 ORDER BY year DESC LIMIT 1"
                ).fetchone()
        if calendar is None:
            return None
        days = conn.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = ? ORDER BY day_number",
            (calendar["id"],),
        ).fetchall()
        archives = conn.execute(
            "SELECT year, title FROM christmas_calendars WHERE published = 1 ORDER BY year DESC"
        ).fetchall()

    open_days = [
        row
        for row in days
        if bool(row["enabled"])
        and (
            preview_unlock_all
            or christmas_day_is_open(calendar["year"], row["day_number"], display_date, True)
        )
    ]
    image_url = calendar["image_url"] or CHRISTMAS_DEFAULT_IMAGE
    doors: list[str] = []
    modals: list[str] = []
    layout_variant = normalize_christmas_layout_variant(calendar["layout_variant"])
    door_positions = christmas_door_positions(calendar["year"], layout_variant)
    puzzle_overlay = christmas_puzzle_overlay_svg(calendar["year"], layout_variant)
    puzzle_clip_definitions = christmas_puzzle_clip_definitions(
        calendar["year"], layout_variant
    )
    for row in days:
        day_number = row["day_number"]
        grid_position = door_positions[day_number - 1]
        grid_row = (grid_position - 1) // 6 + 1
        grid_column = (grid_position - 1) % 6 + 1
        piece_color = "green" if (grid_row + grid_column + layout_variant) % 2 else "red"
        puzzle_tabs = "".join(
            f'<span class="christmas-puzzle-tab is-{direction}" aria-hidden="true"></span>'
            for direction in christmas_puzzle_tabs(
                calendar["year"], layout_variant, grid_row, grid_column
            )
        )
        position_class = f"puzzle-position-{grid_position}"
        enabled = bool(row["enabled"])
        is_open = enabled and (
            preview_unlock_all
            or christmas_day_is_open(calendar["year"], day_number, display_date, True)
        )
        is_missed = christmas_day_can_restore(
            calendar["year"], day_number, display_date, enabled
        )
        can_restore = (
            not is_preview
            and not preview_unlock_all
            and is_missed
        )
        modal_id = f"christmas-day-{calendar['id']}-{day_number}"
        if is_open or can_restore:
            door_state = "is-open is-covered" if is_open else "is-locked is-covered is-past"
            disabled_attribute = "" if is_open else "disabled"
            initial_label = "Découvrir" if is_open else "Rattrapage le 25"
            aria_label = (
                f"Ouvrir la case {day_number} : {row['title']}"
                if is_open
                else f"Case {day_number} déjà passée, disponible au rattrapage le 25 décembre"
            )
            doors.append(
                f"""
                <button class="christmas-door puzzle-piece puzzle-{piece_color} {position_class} {door_state}"
                  type="button" data-christmas-day-open="{modal_id}" data-christmas-day="{day_number}"
                  data-christmas-open-label="Ouvrir la case {day_number} : {e(row['title'])}" {disabled_attribute}
                  aria-controls="{modal_id}" aria-haspopup="dialog" aria-label="{e(aria_label)}">
                  <span class="christmas-piece-art" aria-hidden="true"><img src="{e(image_url)}" alt=""></span>
                  {puzzle_tabs}
                  <span class="christmas-door-number">{day_number}</span>
                  <span class="christmas-door-open-label" data-christmas-day-label>{initial_label}</span>
                </button>
                """
            )
            day_image = (
                f'<img class="christmas-day-image" src="{e(row["image_url"])}" alt="">'
                if row["image_url"]
                else ""
            )
            day_link = (
                f'<a class="button primary" href="{e(row["link_url"])}" target="_blank" rel="noopener noreferrer">{e(row["link_label"] or "En savoir plus")}</a>'
                if row["link_url"] and valid_optional_url(row["link_url"])
                else ""
            )
            modals.append(
                f"""
                <div class="event-modal christmas-modal" id="{modal_id}" role="dialog" aria-modal="true"
                  aria-labelledby="{modal_id}-title" data-christmas-day-modal hidden>
                  <div class="event-modal-backdrop" data-christmas-day-close></div>
                  <article class="event-modal-panel christmas-day-panel" tabindex="-1">
                    <button class="event-modal-close" type="button" aria-label="Fermer" data-christmas-day-close>&times;</button>
                    <p class="christmas-modal-day">{day_number} décembre · {e(CHRISTMAS_CATEGORY_LABELS[normalize_christmas_category(row['category'])])}</p>
                    <h2 id="{modal_id}-title">{e(row['title'])}</h2>
                    {f'<p class="lead">{e(row["teaser"])}</p>' if row['teaser'] else ''}
                    {day_image}
                    <div class="christmas-day-copy">{paragraphs(row['body'])}</div>
                    {day_link}
                  </article>
                </div>
                """
            )
        else:
            locked_label = (
                "Case désactivée"
                if not enabled
                else "Case manquée, disponible au rattrapage le 25 décembre"
                if is_missed
                else f"Disponible le {day_number} décembre {calendar['year']}"
            )
            doors.append(
                f"""
                <button class="christmas-door puzzle-piece puzzle-{piece_color} {position_class} is-locked"
                  type="button" disabled aria-label="Case {day_number}, {e(locked_label)}">
                  {puzzle_tabs}
                  <span class="christmas-door-number">{day_number}</span>
                  <span class="christmas-door-lock" aria-hidden="true">✦</span>
                </button>
                """
            )

    enabled_count = sum(1 for row in days if row["enabled"])
    completion_enabled = bool(calendar["completion_enabled"])
    completion_eligible = (
        completion_enabled
        and enabled_count == 24
        and display_date == date(calendar["year"], 12, 24)
    )
    completion_link = (
        f'<a class="button primary" href="{e(calendar["completion_link_url"])}" target="_blank" rel="noopener noreferrer">{e(calendar["completion_link_label"] or CHRISTMAS_COMPLETION_LINK_LABEL_DEFAULT)}</a>'
        if calendar["completion_link_url"]
        and valid_optional_url(calendar["completion_link_url"])
        else ""
    )
    completion_reopen_button = (
        '<button class="button small christmas-completion-reopen" type="button" data-christmas-completion-open hidden>Voir ma récompense</button>'
        if completion_enabled
        else ""
    )
    completion_modal = (
        f"""
        <div class="event-modal christmas-modal christmas-completion-modal" role="dialog" aria-modal="true"
          aria-labelledby="christmas-completion-title" data-christmas-completion-modal hidden>
          <div class="event-modal-backdrop" data-christmas-completion-close></div>
          <article class="event-modal-panel christmas-day-panel christmas-completion-panel" tabindex="-1">
            <button class="event-modal-close" type="button" aria-label="Fermer" data-christmas-completion-close>&times;</button>
            <div class="christmas-completion-icon" aria-hidden="true">✦</div>
            <p class="christmas-modal-day">24 décembre · Calendrier complété</p>
            <h2 id="christmas-completion-title">{e(calendar['completion_title'] or CHRISTMAS_COMPLETION_TITLE_DEFAULT)}</h2>
            <div class="christmas-completion-copy">{paragraphs(calendar['completion_message'] or CHRISTMAS_COMPLETION_MESSAGE_DEFAULT)}</div>
            {completion_link}
            <small>Cette réussite est enregistrée avec votre progression sur cet appareil.</small>
          </article>
        </div>
        """
        if completion_enabled
        else ""
    )
    progress = f'<span data-christmas-discovered-count>0</span> / {enabled_count} cases découvertes'
    archive_links = "".join(
        f'<a class="album-filter {"is-active" if row["year"] == calendar["year"] else ""}" href="/noel?annee={row["year"]}">{row["year"]}</a>'
        for row in archives
    )
    preview_label = (
        "toutes les cases déverrouillées"
        if preview_unlock_all
        else f"date simulée : {format_date(display_date.isoformat())}"
    )
    preview_banner = (
        f"""
        <div class="christmas-preview-banner">
          <strong>Mode test · {preview_label}</strong>
          <a class="button small secondary" href="/admin/noel/{calendar['id']}">Retour à l’édition</a>
        </div>
        """
        if is_preview
        else ""
    )
    body = f"""
    <style nonce="{CSP_NONCE_PLACEHOLDER}">.christmas-theme{{--christmas-accent:{normalize_hex_color(calendar['accent_color'])}}}</style>
    <div class="christmas-theme">
    {preview_banner}
    <section class="christmas-hero">
      <div class="christmas-hero-aura" aria-hidden="true"></div>
      <div class="christmas-hero-copy">
        <p class="eyebrow"><span></span>{e(calendar['eyebrow'] or 'Calendrier de l’Avent')}</p>
        <h1>{e(calendar['title'])}</h1>
        <p>{e(calendar['intro'] or '')}</p>
        <div class="christmas-progress">
          <strong>{progress}</strong>
          <span>{len(open_days)} case{'s' if len(open_days) != 1 else ''} disponible{'s' if len(open_days) != 1 else ''} aujourd’hui.</span>
        </div>
      </div>
      <div class="christmas-season-stamp" aria-label="Édition {calendar['year']}">
        <span>{calendar['year']}</span>
        <small>24 fragments<br>1 image mystère</small>
      </div>
    </section>
    <section class="section christmas-section">
      <div class="christmas-stage">
        <div class="christmas-calendar-head">
          <div>
            <p class="eyebrow">Expérience interactive · Décembre {calendar['year']}</p>
            <h2>Une image. 24 fragments.<br><em>Votre mois de décembre.</em></h2>
          </div>
          {f'<div class="album-filters christmas-years" aria-label="Archives de Noël">{archive_links}</div>' if len(archives) > 1 and not is_preview else ''}
        </div>
        {'' if is_preview else '''
        <aside class="christmas-progress-consent" data-christmas-progress-notice>
          <span class="christmas-consent-icon" aria-hidden="true">◎</span>
          <div>
            <strong>Retrouvez votre image là où vous l’avez laissée</strong>
            <p>Avec votre accord, les cases découvertes sont enregistrées dans un cookie sur cet appareil. Si vous supprimez vos cookies ou changez de navigateur, votre progression sera perdue.</p>
            <small data-christmas-progress-status>Autorisation à choisir dans la gestion des cookies.</small>
          </div>
          <button class="button small secondary" type="button" data-cookie-open>Gérer l’autorisation</button>
        </aside>
        '''}
        <div class="christmas-board-frame">
          <div class="christmas-board-meta" aria-hidden="true">
            <span><i></i> Image en cours de révélation</span>
            <span>6 × 4 · 24 pièces</span>
          </div>
          <div class="christmas-picture-board" aria-label="Calendrier de l’Avent {calendar['year']}"
            data-christmas-calendar data-christmas-year="{calendar['year']}" data-christmas-preview="{'1' if is_preview else '0'}"
            data-christmas-completion-eligible="{'1' if completion_eligible else '0'}" data-christmas-completion-required="{enabled_count}">
            <img class="christmas-reveal-image" src="{e(image_url)}" alt="Image mystère du calendrier de l’Avent {calendar['year']}">
            <div class="christmas-board-vignette" aria-hidden="true"></div>
            {puzzle_clip_definitions}
            <div class="christmas-doors">{"".join(doors)}</div>
            {puzzle_overlay}
          </div>
          <div class="christmas-board-caption">
            <p><span aria-hidden="true">↗</span> Du 1er au 24, une seule nouvelle case s’ouvre chaque jour. Dès le 25 décembre, toutes les cases oubliées peuvent être rattrapées.</p>
            {completion_reopen_button}
            <span class="christmas-board-signature">Vert-Tige · {calendar['year']}</span>
          </div>
        </div>
      </div>
    </section>
    {"".join(modals)}
    {completion_modal}
    </div>
    """
    return layout(
        f"Calendrier de l’Avent {calendar['year']}",
        body,
        "/noel",
        description=compact_text(calendar["intro"], calendar["title"], 160),
        image_url=image_url,
        indexable=not is_preview,
        cookie_controls_enabled=not is_preview,
    )


def admin_shell(title: str, content: str, tab: str = "/admin") -> str:
    tabs = "".join(
        [
            nav_link("/admin", "Tableau de bord", tab),
            nav_link("/admin/home", "Accueil", tab),
            nav_link("/admin/practical", "Infos pratiques", tab),
            nav_link("/admin/events", "Programmation", tab),
            nav_link("/admin/articles", "Articles", tab),
            nav_link("/admin/noel", "Noël", tab),
            nav_link("/admin/photos", "Photos", tab),
            nav_link("/admin/messages", "Messages", tab),
            nav_link("/admin/users", "Comptes", tab),
            nav_link("/admin/maintenance", "Maintenance", tab),
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
            "christmas": conn.execute("SELECT COUNT(*) AS count FROM christmas_calendars").fetchone()["count"],
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
            ("éditions de Noël", counts["christmas"]),
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
      <a class="admin-action" href="/admin/noel"><strong>Calendrier de l’Avent</strong><span>Préparer une édition annuelle, ses 24 cases et tester les dates d’ouverture.</span></a>
      <a class="admin-action" href="/admin/photos"><strong>Ajouter des photos</strong><span>Alimenter la banque d’images du jardin.</span></a>
      <a class="admin-action" href="/admin/maintenance"><strong>Sauvegardes et logs</strong><span>Créer un backup, télécharger les données utiles et consulter le journal serveur.</span></a>
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
    logo_url = settings.get("logo_url") or DEFAULT_SETTINGS["logo_url"]
    logo_preview = f'<img class="logo-preview" src="{e(logo_url)}" alt="Logo actuel">'
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
          <button class="button small secondary" type="button" data-reset-logo data-default-src="{e(DEFAULT_SETTINGS['logo_url'])}">Retour à zéro</button>
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
        <label>Validation Google Search Console (balise HTML)<input name="google_site_verification" value="{e(settings.get('google_site_verification', ''))}" placeholder="Valeur du champ content de la balise Google"></label>
        <p class="form-note">Ce champ concerne la validation par balise HTML. Pour une validation de domaine par DNS, ajoute l’enregistrement TXT fourni par Google chez le gestionnaire de ton domaine.</p>
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
    image_url = row["image_url"] if row else ""
    description = row["description"] if row else ""
    with connect() as conn:
        photos = conn.execute(
            """
            SELECT p.*, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    photo_options = photo_library_options(photos, image_url)
    current_preview = (
        f'<img class="cover-preview" src="{e(image_url)}" alt="Image ou affiche actuelle">'
        if image_url
        else '<div class="empty-state compact">Aucune image associée.</div>'
    )
    return f"""
    <form class="form-panel" method="post" action="{action}" enctype="multipart/form-data">
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
      <div class="image-picker">
        <div>
          <p class="field-label">Photo ou affiche</p>
          {current_preview}
        </div>
        <div class="image-picker-controls">
          <input type="hidden" name="current_image_url" value="{e(image_url)}">
          <label>Choisir dans la galerie
            <select name="event_image_choice">
              <option value="">Conserver l’image actuelle</option>
              <option value="__none__">Aucune image</option>
              {photo_options}
            </select>
          </label>
          <label>Ou envoyer une nouvelle image
            <input type="file" name="event_image" accept="image/*">
          </label>
          <p class="form-note">Une image envoyée ici sera ajoutée à la galerie et associée à l’événement.</p>
        </div>
      </div>
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
    return admin_shell("Programmation", content, "/admin/events")


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
            "SELECT * FROM photos WHERE visibility IN ('article', 'both', 'library') ORDER BY created_at DESC"
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


def admin_christmas_guide_page() -> str:
    content = """
    <div class="admin-toolbar christmas-guide-toolbar">
      <a class="button secondary" href="/admin/noel">← Toutes les éditions</a>
    </div>
    <div class="christmas-guide">
      <section class="info-panel christmas-admin-help christmas-guide-intro">
        <p class="eyebrow">Le guide de l’équipe</p>
        <h2>Préparer Noël, pas à pas</h2>
        <p>Une édition par année, une image et 24 surprises. Suivez ces six étapes pour préparer, tester et publier le calendrier depuis cet espace de gestion.</p>
        <p><strong>Le réflexe à garder :</strong> enregistrez chaque formulaire avant de changer de page ou d’ouvrir un aperçu.</p>
      </section>
      <nav class="christmas-guide-contents" aria-label="Sommaire du tutoriel de Noël">
        <a href="#guide-edition">1. Créer l’édition</a>
        <a href="#guide-image">2. Choisir l’image</a>
        <a href="#guide-cases">3. Remplir les cases</a>
        <a href="#guide-cadeau">4. Préparer la finale</a>
        <a href="#guide-test">5. Tout tester</a>
        <a href="#guide-publication">6. Publier</a>
      </nav>
      <div class="christmas-guide-steps">
        <section class="christmas-guide-step" id="guide-edition" aria-labelledby="guide-edition-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">01</span><h2 id="guide-edition-title">Créer l’édition de l’année</h2></div>
          <ol>
            <li>Dans <strong>Administration → Noël</strong>, renseignez l’année dans « Préparer une nouvelle année ».</li>
            <li>Choisissez les <strong>24 propositions prêtes à adapter</strong> ou une ancienne édition comme point de départ, puis cliquez sur <strong>Créer l’édition</strong>.</li>
            <li>Personnalisez le titre, le texte d’introduction et la couleur principale dans les réglages.</li>
          </ol>
          <p class="christmas-guide-tip">Une copie reprend les contenus, l’image et les réglages du message final. Elle est créée en brouillon : relisez les dates et les éventuelles modalités du cadeau pour la nouvelle année.</p>
        </section>
        <section class="christmas-guide-step" id="guide-image" aria-labelledby="guide-image-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">02</span><h2 id="guide-image-title">Choisir l’image et son puzzle</h2></div>
          <ol>
            <li>Choisissez une image dans la bibliothèque ou utilisez <strong>Ou envoyer une nouvelle image</strong>. Privilégiez une image horizontale au format <strong>3:2</strong>, par exemple 1 800 × 1 200 pixels.</li>
            <li>Regardez le <strong>Gabarit de découpe réel</strong> : il montre les contours des 24 pièces et le jour qui révélera chaque détail. Le découpage est automatique.</li>
            <li>Essayez les 12 choix de <strong>Disposition des pièces</strong> pour mélanger les numéros. Utilisez <strong>Masquer les repères</strong> ou <strong>Télécharger le gabarit PNG</strong> pour préparer le visuel.</li>
            <li>Cliquez sur <strong>Enregistrer les réglages</strong>.</li>
          </ol>
          <p class="christmas-guide-tip">Les numéros du gabarit servent à vous guider. Importez l’image sans numéros ni traits : le site dessine les pièces par-dessus. L’image importée reste dans la bibliothèque sans être ajoutée à la galerie publique.</p>
        </section>
        <section class="christmas-guide-step" id="guide-cases" aria-labelledby="guide-cases-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">03</span><h2 id="guide-cases-title">Remplir les 24 surprises</h2></div>
          <ol>
            <li>En bas des réglages, cliquez sur un jour dans <strong>Les 24 cases</strong>.</li>
            <li>Choisissez la catégorie, puis rédigez le <strong>titre</strong>, une courte accroche et le <strong>contenu</strong> : recette, conseil jardinage, atelier, souvenir du jardin…</li>
            <li>Ajoutez, si utile, une illustration et un lien HTTPS avec son libellé. L’illustration accompagne le contenu ; l’image mystère reste commune à tout le puzzle.</li>
            <li>Gardez <strong>Case active</strong> cochée, cliquez sur <strong>Enregistrer la case</strong>, puis passez au jour suivant.</li>
          </ol>
          <p class="christmas-guide-tip">Une case désactivée reste fermée, y compris en test. Pour un calendrier complet et le message final du 24 décembre, les 24 cases doivent être actives.</p>
        </section>
        <section class="christmas-guide-step" id="guide-cadeau" aria-labelledby="guide-cadeau-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">04</span><h2 id="guide-cadeau-title">Préparer les félicitations et le cadeau</h2></div>
          <ol>
            <li>Dans les réglages de l’édition, ouvrez la partie <strong>Félicitations et cadeau éventuel</strong> et cochez <strong>Activer le message final</strong>.</li>
            <li>Personnalisez le titre et le message. Si l’association offre un cadeau, précisez quoi, où, quand et comment le récupérer.</li>
            <li>Ajoutez éventuellement un lien HTTPS et le texte de son bouton, puis <strong>Enregistrer les réglages</strong>.</li>
          </ol>
          <p>Le message s’affiche <strong>le 24 décembre uniquement</strong>, une fois les 24 cases découvertes, à la fermeture de la dernière surprise. Le bouton <strong>Voir ma récompense</strong> permet de le rouvrir ce jour-là. Le rattrapage à partir du 25 ne déclenche pas cette finale.</p>
          <p class="christmas-guide-tip">Exemple à adapter : « Bravo pour les 24 surprises ! Retrouvez l’équipe au jardin le [date] entre [horaires] pour recevoir [cadeau]. » L’association organise la remise selon les modalités indiquées.</p>
        </section>
        <section class="christmas-guide-step" id="guide-test" aria-labelledby="guide-test-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">05</span><h2 id="guide-test-title">Tout vérifier avant l’ouverture</h2></div>
          <ol>
            <li><strong>Enregistrez vos réglages et vos cases</strong> avant de lancer un test. L’aperçu affiche la dernière version enregistrée.</li>
            <li>Cliquez sur <strong>Tester les 24 cases</strong> : toutes les cases actives sont déverrouillées, même hors décembre et pour une édition en brouillon. Ouvrez les 24 surprises et fermez la dernière pour vérifier le message final.</li>
            <li>Pour contrôler les règles du site, choisissez une date dans <strong>Tester à la date du</strong>, puis cliquez sur <strong>Ouvrir l’aperçu</strong>. Par exemple : le 12 pour une journée normale, le 25 pour le rattrapage.</li>
          </ol>
          <p class="christmas-guide-tip">Le test est réservé à l’administration. Il ne mémorise pas les découvertes dans le cookie visiteur : rechargez l’aperçu pour recommencer. Un aperçu à une date précise garde les restrictions du jour ; utilisez « Tester les 24 cases » pour tout ouvrir.</p>
        </section>
        <section class="christmas-guide-step" id="guide-publication" aria-labelledby="guide-publication-title">
          <div class="christmas-guide-step-heading"><span aria-hidden="true">06</span><h2 id="guide-publication-title">Publier et préparer la suite</h2></div>
          <ol>
            <li>Vérifiez l’année, l’image, les 24 contenus actifs et les modalités du cadeau éventuel.</li>
            <li>Cochez <strong>Publier cette édition</strong> et, pour ajouter l’accès dans la navigation, <strong>Afficher « Noël » dans le menu pendant le mois de décembre</strong>.</li>
            <li>Cliquez sur <strong>Enregistrer les réglages</strong>. Vous pouvez préparer la publication en avance : le module public est accessible <strong>du 1er au 31 décembre inclus</strong>.</li>
            <li>L’année suivante, revenez à <strong>Noël → Préparer une nouvelle année</strong> et choisissez cette édition comme point de départ.</li>
          </ol>
          <p class="christmas-guide-tip">Pendant décembre, les changements enregistrés sur une édition publiée sont visibles par les visiteurs. Préparez et testez d’abord en brouillon.</p>
        </section>
      </div>
      <section class="christmas-guide-faq" aria-labelledby="guide-questions-title">
        <p class="eyebrow">Les réponses à garder sous la main</p>
        <h2 id="guide-questions-title">Questions fréquentes</h2>
        <details>
          <summary>Pourquoi le calendrier ou l’onglet Noël n’apparaît-il pas sur le site ?</summary>
          <p>Le module public est réservé au mois de décembre. Vérifiez aussi qu’une édition de l’année concernée est publiée. Pour afficher le lien dans la navigation, cochez l’option du menu et enregistrez. L’administration et ses aperçus restent accessibles toute l’année.</p>
        </details>
        <details>
          <summary>Pourquoi certaines cases sont-elles bloquées ?</summary>
          <p>Du 1er au 24 décembre, seule la case du jour peut être découverte. Les cases déjà découvertes restent consultables ; les jours manqués attendent le rattrapage, du 25 au 31 décembre. En aperçu daté, ces règles s’appliquent aussi. En test complet, vérifiez que la case est active si elle reste bloquée.</p>
        </details>
        <details>
          <summary>Comment la progression des visiteurs est-elle conservée ?</summary>
          <p>Le visiteur choisit s’il autorise la sauvegarde dans un cookie sur son appareil. Sans accord, il peut consulter les cases disponibles, mais son avancement n’est pas mémorisé après rechargement. Supprimer les cookies, changer de navigateur ou d’appareil fait perdre l’accès à la progression enregistrée. Le choix se retrouve dans « Gérer l’autorisation » sur le calendrier.</p>
        </details>
        <details>
          <summary>Pourquoi le message final ne s’affiche-t-il pas ?</summary>
          <p>Vérifiez que « Activer le message final » est coché, que les 24 cases sont actives et que les réglages sont enregistrés. En visite normale, il faut avoir découvert les 24 cases le 24 décembre. Pour tester cette séquence, ouvrez « Tester les 24 cases », découvrez-les toutes, puis fermez la dernière surprise.</p>
        </details>
        <details>
          <summary>Pourquoi mes modifications n’apparaissent-elles pas dans l’aperçu ?</summary>
          <p>Enregistrez le formulaire concerné avec « Enregistrer les réglages » ou « Enregistrer la case », puis rechargez l’aperçu déjà ouvert. Le choix d’une nouvelle image ou d’une disposition dans le formulaire prépare la modification ; l’enregistrement l’applique.</p>
        </details>
      </section>
      <div class="admin-toolbar christmas-guide-toolbar"><a class="button primary" href="/admin/noel">Préparer mon calendrier</a><a class="text-link" href="#guide-edition">Revenir à la première étape ↑</a></div>
    </div>
    """
    return admin_shell("Mode d’emploi · Noël", content, "/admin/noel")


def admin_christmas_page(query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, COUNT(d.id) AS day_count,
                   SUM(CASE WHEN d.enabled = 1 THEN 1 ELSE 0 END) AS enabled_count
            FROM christmas_calendars c
            LEFT JOIN christmas_days d ON d.calendar_id = c.id
            GROUP BY c.id
            ORDER BY c.year DESC
            """
        ).fetchall()
    source_options = "".join(
        f'<option value="{row["id"]}" {"selected" if index == 0 else ""}>{row["year"]} · {e(row["title"])}</option>'
        for index, row in enumerate(rows)
    )
    row_html = "".join(
        f"""
        <tr>
          <td><strong>{row['year']}</strong><span>{'Publié' if row['published'] else 'Brouillon'} · {row['enabled_count'] or 0}/24 cases actives</span></td>
          <td><strong>{e(row['title'])}</strong><span>{'Visible dans le menu en décembre' if row['show_in_nav'] else 'Masqué du menu'}</span></td>
          <td class="actions">
            <a class="button small secondary" href="/admin/noel/{row['id']}">Configurer</a>
            <a class="button small secondary" href="/admin/noel/{row['id']}/preview?mode=all" target="_blank">Tester les 24 cases</a>
            <form method="post" action="/admin/noel/{row['id']}/delete"><button class="button small danger" type="submit">Supprimer</button></form>
          </td>
        </tr>
        """
        for row in rows
    )
    status = query.get("status", [""])[0]
    notices = {
        "created": '<div class="notice success">La nouvelle édition et ses 24 cases sont prêtes à être personnalisées.</div>',
        "duplicate": '<div class="notice success">L’édition a été dupliquée en brouillon avec ses 24 contenus.</div>',
        "exists": '<div class="notice error">Une édition existe déjà pour cette année.</div>',
        "invalid": '<div class="notice error">Choisis une année comprise entre 2020 et 2100.</div>',
        "deleted": '<div class="notice success">L’édition a été supprimée.</div>',
    }
    content = f"""
    {notices.get(status, '')}
    <div class="admin-two-column christmas-admin-intro">
      <form class="form-panel" method="post" action="/admin/noel/create">
        <h2>Préparer une nouvelle année</h2>
        <label>Année<input type="number" name="year" min="2020" max="2100" value="{max(date.today().year, 2026) + 1}" required></label>
        <label>Point de départ
          <select name="source_calendar_id">
            <option value="" {"selected" if not rows else ""}>24 propositions prêtes à adapter</option>
            {source_options}
          </select>
        </label>
        <p class="form-note">Une copie reprend l’image, les textes, les couleurs et les 24 cases, mais reste en brouillon jusqu’à publication.</p>
        <button class="button primary" type="submit">Créer l’édition</button>
      </form>
      <div class="info-panel christmas-admin-help">
        <p class="eyebrow">Le guide de l’équipe</p>
        <h2>Préparer Noël, pas à pas</h2>
        <p>Créer l’année, choisir l’image et son puzzle, remplir les surprises, préparer le cadeau, tester et publier : retrouvez toutes les étapes et les réponses aux questions fréquentes.</p>
        <div><a class="button secondary" href="/admin/noel/guide">Ouvrir le mode d’emploi</a></div>
      </div>
    </div>
    <div class="section-heading admin-section-heading"><div><p class="eyebrow">Éditions</p><h2>Calendriers disponibles</h2></div></div>
    <table class="admin-table christmas-admin-table">
      <thead><tr><th>Année</th><th>Présentation</th><th></th></tr></thead>
      <tbody>{row_html or '<tr><td colspan="3">Aucune édition.</td></tr>'}</tbody>
    </table>
    """
    return admin_shell("Noël", content, "/admin/noel")


def admin_christmas_edit_page(calendar_id: int, query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    with connect() as conn:
        calendar = conn.execute(
            "SELECT * FROM christmas_calendars WHERE id = ?", (calendar_id,)
        ).fetchone()
        if calendar is None:
            return not_found_page()
        days = conn.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = ? ORDER BY day_number",
            (calendar_id,),
        ).fetchall()
        photos = conn.execute(
            """
            SELECT p.*, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    image_url = calendar["image_url"] or CHRISTMAS_DEFAULT_IMAGE
    photo_options = photo_library_options(photos, image_url)
    layout_variant = normalize_christmas_layout_variant(calendar["layout_variant"])
    cut_layouts = {
        str(variant): christmas_door_positions(calendar["year"], variant)
        for variant in range(1, 13)
    }
    current_positions = cut_layouts[str(layout_variant)]
    day_by_position = {
        position: day_number
        for day_number, position in enumerate(current_positions, start=1)
    }
    cut_cells = "".join(
        f"""
        <span class="christmas-cut-cell" data-cut-position="{position}">
          <span class="christmas-cut-number" data-cut-number>{day_by_position[position]}</span>
        </span>
        """
        for position in range(1, 25)
    )
    cut_overlay = christmas_puzzle_overlay_svg(calendar["year"], layout_variant, admin=True)
    day_rows = "".join(
        f"""
        <a class="christmas-admin-day {'is-disabled' if not row['enabled'] else ''}" href="/admin/noel/{calendar_id}/jours/{row['day_number']}">
          <span class="christmas-admin-day-number">{row['day_number']}</span>
          <span><strong>{e(row['title'])}</strong><small>{e(CHRISTMAS_CATEGORY_LABELS[normalize_christmas_category(row['category'])])}{' · masquée' if not row['enabled'] else ''}</small></span>
        </a>
        """
        for row in days
    )
    status = query.get("status", [""])[0]
    notices = {
        "saved": '<div class="notice success">Les réglages de l’édition ont été enregistrés.</div>',
        "created": '<div class="notice success">L’édition et ses 24 cases sont prêtes à être personnalisées.</div>',
        "duplicate": '<div class="notice success">L’édition a été dupliquée en brouillon avec ses 24 contenus.</div>',
    }
    notice = notices.get(status, "")
    published = "checked" if calendar["published"] else ""
    show_in_nav = "checked" if calendar["show_in_nav"] else ""
    completion_enabled = "checked" if calendar["completion_enabled"] else ""
    content = f"""
    {notice}
    <div class="christmas-admin-toolbar">
      <div class="button-row">
        <a class="button secondary" href="/admin/noel">← Toutes les éditions</a>
        <a class="button secondary" href="/admin/noel/guide" target="_blank" rel="noopener" title="Ouvrir le mode d’emploi dans un nouvel onglet">Mode d’emploi ↗</a>
      </div>
      <form class="christmas-test-form" method="get" action="/admin/noel/{calendar_id}/preview" target="_blank">
        <label>Tester à la date du <input type="date" name="date" value="{calendar['year']}-12-12"></label>
        <button class="button primary" type="submit">Ouvrir l’aperçu</button>
        <a class="button secondary" href="/admin/noel/{calendar_id}/preview?mode=all" target="_blank">Tester les 24 cases</a>
      </form>
    </div>
    <form class="form-panel christmas-settings-form" method="post" action="/admin/noel/{calendar_id}/save" enctype="multipart/form-data">
      <div class="section-heading admin-section-heading"><div><p class="eyebrow">Édition {calendar['year']}</p><h2>Présentation et publication</h2></div></div>
      <div class="form-row">
        <label>Sur-titre<input name="eyebrow" value="{e(calendar['eyebrow'] or '')}"></label>
        <label>Couleur principale<input type="color" name="accent_color" value="{normalize_hex_color(calendar['accent_color'])}"></label>
      </div>
      <label>Disposition des pièces
        <select name="layout_variant" data-christmas-layout-select>{christmas_layout_options(layout_variant)}</select>
        <span class="form-note">Douze mélanges sont disponibles. Les numéros restent accessibles dans l’ordre au clavier, mais sont dispersés visuellement dans le puzzle.</span>
      </label>
      <label>Titre<input name="title" value="{e(calendar['title'])}" required></label>
      <label>Texte d’introduction<textarea name="intro" rows="4">{e(calendar['intro'] or '')}</textarea></label>
      <div class="image-picker christmas-image-picker" data-christmas-cut-template
        data-christmas-year="{calendar['year']}"
        data-current-image="{e(image_url)}"
        data-default-image="{e(CHRISTMAS_DEFAULT_IMAGE)}"
        data-cut-layouts="{e(json.dumps(cut_layouts, separators=(',', ':')))}">
        <div class="christmas-cut-preview">
          <div class="christmas-cut-preview-heading">
            <div><p class="field-label">Image mystère</p><strong>Gabarit de découpe réel</strong></div>
            <span>6 colonnes × 4 lignes</span>
          </div>
          <div class="christmas-cut-canvas">
            <img class="cover-preview christmas-cover-preview" src="{e(image_url)}" alt="Image actuelle du calendrier" data-christmas-cut-image>
            {cut_overlay}
            <div class="christmas-cut-grid" aria-label="Découpage de l’image en 24 cases" data-christmas-cut-grid>{cut_cells}</div>
          </div>
          <div class="christmas-cut-actions">
            <button class="button small secondary" type="button" data-christmas-cut-toggle>Masquer les repères</button>
            <button class="button small secondary" type="button" data-christmas-cut-download>Télécharger le gabarit PNG</button>
          </div>
          <p class="form-note">Les traits et numéros sont réservés à l’administration. Ils montrent exactement quel détail sera révélé par chaque jour.</p>
        </div>
        <div class="image-picker-controls">
          <input type="hidden" name="current_image_url" value="{e(image_url)}">
          <label>Choisir dans la bibliothèque
            <select name="image_choice" data-christmas-image-choice>
              <option value="">Conserver l’image actuelle</option>
              <option value="__none__">Aucune image (visuel par défaut)</option>
              {photo_options}
            </select>
          </label>
          <label>Ou envoyer une nouvelle image<input type="file" name="christmas_image" accept="image/*" data-christmas-image-file></label>
          <p class="form-note">Choisis idéalement une image horizontale au format 3:2. Elle sera automatiquement découpée en 24 fragments (6 × 4) et conservée dans la bibliothèque sans être ajoutée à la galerie publique.</p>
        </div>
      </div>
      <section class="christmas-reward-settings">
        <div class="section-heading admin-section-heading">
          <div><p class="eyebrow">24 décembre</p><h2>Félicitations et cadeau éventuel</h2></div>
          <label class="christmas-reward-toggle"><input type="checkbox" name="completion_enabled" value="1" {completion_enabled}> Activer le message final</label>
        </div>
        <label>Titre de félicitations<input name="completion_title" value="{e(calendar['completion_title'] or CHRISTMAS_COMPLETION_TITLE_DEFAULT)}"></label>
        <label>Message final ou modalités du cadeau<textarea name="completion_message" rows="4">{e(calendar['completion_message'] or CHRISTMAS_COMPLETION_MESSAGE_DEFAULT)}</textarea></label>
        <div class="form-row">
          <label>Texte du bouton facultatif<input name="completion_link_label" value="{e(calendar['completion_link_label'] or CHRISTMAS_COMPLETION_LINK_LABEL_DEFAULT)}"></label>
          <label>Lien HTTPS facultatif<input type="url" name="completion_link_url" value="{e(calendar['completion_link_url'] or '')}" placeholder="https://..."></label>
        </div>
        <p class="form-note">Le message apparaît uniquement le 24 décembre, après la découverte des 24 cases actives. Le mode « Tester les 24 cases » permet de vérifier entièrement cette séquence.</p>
      </section>
      <div class="check-row">
        <label><input type="checkbox" name="published" value="1" {published}> Publier cette édition</label>
        <label><input type="checkbox" name="show_in_nav" value="1" {show_in_nav}> Afficher « Noël » dans le menu pendant le mois de décembre</label>
      </div>
      <button class="button primary" type="submit">Enregistrer les réglages</button>
    </form>
    <div class="section-heading admin-section-heading"><div><p class="eyebrow">Contenus</p><h2>Les 24 cases</h2></div><span class="form-note">Chaque case peut être modifiée ou masquée.</span></div>
    <div class="christmas-admin-days">{day_rows}</div>
    """
    return admin_shell(f"Noël {calendar['year']}", content, "/admin/noel")


def admin_christmas_day_page(calendar_id: int, day_number: int, query: dict[str, list[str]] | None = None) -> str:
    if day_number < 1 or day_number > 24:
        return not_found_page()
    query = query or {}
    with connect() as conn:
        calendar = conn.execute(
            "SELECT * FROM christmas_calendars WHERE id = ?", (calendar_id,)
        ).fetchone()
        row = conn.execute(
            "SELECT * FROM christmas_days WHERE calendar_id = ? AND day_number = ?",
            (calendar_id, day_number),
        ).fetchone()
        photos = conn.execute(
            """
            SELECT p.*, a.name AS album_name
            FROM photos p
            LEFT JOIN photo_albums a ON a.id = p.album_id
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    if calendar is None or row is None:
        return not_found_page()
    image_url = row["image_url"] or ""
    current_preview = (
        f'<img class="cover-preview" src="{e(image_url)}" alt="Illustration actuelle de la case">'
        if image_url
        else '<div class="empty-state compact">Cette case utilise uniquement l’image mystère.</div>'
    )
    photo_options = photo_library_options(photos, image_url)
    enabled = "checked" if row["enabled"] else ""
    previous_link = (
        f'<a class="button secondary" href="/admin/noel/{calendar_id}/jours/{day_number - 1}">← Jour {day_number - 1}</a>'
        if day_number > 1
        else '<span></span>'
    )
    next_link = (
        f'<a class="button secondary" href="/admin/noel/{calendar_id}/jours/{day_number + 1}">Jour {day_number + 1} →</a>'
        if day_number < 24
        else '<span></span>'
    )
    notice = (
        '<div class="notice success">La case a été enregistrée.</div>'
        if query.get("status") == ["saved"]
        else ""
    )
    content = f"""
    {notice}
    <div class="christmas-day-nav">{previous_link}<a class="text-link" href="/admin/noel/{calendar_id}">Toutes les cases</a>{next_link}</div>
    <p class="christmas-guide-context">Besoin d’aide pour cette case ? <a class="text-link" href="/admin/noel/guide#guide-cases" target="_blank" rel="noopener">Consulter le mode d’emploi ↗</a></p>
    <form class="form-panel" method="post" action="/admin/noel/{calendar_id}/jours/{day_number}" enctype="multipart/form-data">
      <div class="section-heading admin-section-heading"><div><p class="eyebrow">{day_number} décembre {calendar['year']}</p><h2>Contenu de la case</h2></div></div>
      <div class="form-row">
        <label>Catégorie<select name="category">{christmas_category_options(row['category'])}</select></label>
        <label class="christmas-enabled-check"><span>Disponibilité</span><span class="inline-check"><input type="checkbox" name="enabled" value="1" {enabled}> Case active</span></label>
      </div>
      <label>Titre<input name="title" value="{e(row['title'])}" required></label>
      <label>Accroche<input name="teaser" value="{e(row['teaser'] or '')}" placeholder="Une phrase courte affichée dans la surprise"></label>
      <label>Contenu<textarea name="body" rows="8" required>{e(row['body'] or '')}</textarea></label>
      <div class="image-picker">
        <div><p class="field-label">Illustration facultative</p>{current_preview}</div>
        <div class="image-picker-controls">
          <input type="hidden" name="current_image_url" value="{e(image_url)}">
          <label>Choisir dans la bibliothèque
            <select name="image_choice">
              <option value="">Conserver l’image actuelle</option>
              <option value="__none__">Aucune illustration</option>
              {photo_options}
            </select>
          </label>
          <label>Ou envoyer une nouvelle image<input type="file" name="day_image" accept="image/*"></label>
        </div>
      </div>
      <div class="form-row">
        <label>Lien facultatif (HTTPS)<input type="url" name="link_url" value="{e(row['link_url'] or '')}" placeholder="https://..."></label>
        <label>Libellé du lien<input name="link_label" value="{e(row['link_label'] or '')}" placeholder="En savoir plus"></label>
      </div>
      <button class="button primary" type="submit">Enregistrer la case</button>
    </form>
    """
    return admin_shell(f"Noël {calendar['year']} · jour {day_number}", content, "/admin/noel")


def admin_christmas_preview_page(calendar_id: int, query: dict[str, list[str]] | None = None) -> str | None:
    query = query or {}
    with connect() as conn:
        calendar = conn.execute(
            "SELECT year FROM christmas_calendars WHERE id = ?", (calendar_id,)
        ).fetchone()
    if calendar is None:
        return None
    unlock_all = query.get("mode", [""])[0] == "all"
    raw_date = query.get("date", [f"{calendar['year']}-12-24"])[0]
    try:
        simulated_date = date.fromisoformat(raw_date)
    except ValueError:
        simulated_date = date(calendar["year"], 12, 24)
    return christmas_calendar_page(
        today=simulated_date,
        preview_calendar_id=calendar_id,
        preview_unlock_all=unlock_all,
    )


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
    <p class="form-note">Bibliothèque uniquement : photo conservée pour les administrateurs, absente de la galerie publique. Une image utilisée dans un contenu publié reste visible dans ce contenu.</p>
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


def backup_created_label(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    except OSError:
        return ""


def admin_maintenance_page(query: dict[str, list[str]] | None = None) -> str:
    query = query or {}
    status = query.get("status", [""])[0]
    notices = {
        "backup-created": '<div class="notice success">Sauvegarde créée. Elle est disponible dans la liste ci-dessous.</div>',
        "backup-deleted": '<div class="notice success">Sauvegarde supprimée.</div>',
        "backup-error": '<div class="notice error">Impossible de créer la sauvegarde. Consulte le journal serveur pour le détail.</div>',
        "delete-error": '<div class="notice error">Impossible de supprimer cette sauvegarde.</div>',
    }
    notice = notices.get(status, "")
    backups = list_backup_files()
    with connect() as conn:
        admin_logs = conn.execute(
            "SELECT * FROM admin_activity_logs ORDER BY id DESC LIMIT 120"
        ).fetchall()
    backup_rows = "".join(
        f"""
        <tr>
          <td><strong>{e(path.name)}</strong><span>{backup_created_label(path)}</span></td>
          <td>{file_size_label(path.stat().st_size)}</td>
          <td>
            <div class="table-form maintenance-actions">
              <a class="button small secondary" href="/admin/maintenance/backups/{quote(path.name)}">Télécharger</a>
              <form method="post" action="/admin/maintenance/backups/{quote(path.name)}/delete">
                <button class="button small danger" type="submit">Supprimer</button>
              </form>
            </div>
          </td>
        </tr>
        """
        for path in backups
    )
    admin_log_rows = "".join(
        f"""
        <tr>
          <td><strong>{format_datetime(row['created_at'])}</strong><span>{e(row['ip_address'] or '')}</span></td>
          <td>{e(row['username'])}</td>
          <td><strong>{e(row['action'])}</strong><span>{e(row['details'] or '')}</span></td>
          <td>{e(row['target'] or '')}</td>
        </tr>
        """
        for row in admin_logs
    )
    log_lines = "\n".join(e(line) for line in recent_log_lines())
    if not log_lines:
        log_lines = "Aucune ligne de journal pour le moment."
    content = f"""
    {notice}
    <div class="admin-two-column maintenance-grid">
      <section class="form-panel">
        <h2>Sauvegardes</h2>
        <p class="form-note">Une sauvegarde contient la base de données, les images envoyées dans la galerie et les journaux locaux. Elle est à conserver hors du serveur après téléchargement.</p>
        <form method="post" action="/admin/maintenance/backups/create">
          <button class="button primary" type="submit">Créer une sauvegarde maintenant</button>
        </form>
      </section>
      <section class="form-panel">
        <h2>Journal serveur</h2>
        <p class="form-note">Le journal aide à comprendre les connexions, erreurs et actions d’administration récentes.</p>
        <a class="button secondary" href="/admin/maintenance/logs/server-log.txt">Télécharger le journal complet</a>
      </section>
    </div>
    <section class="maintenance-section">
      <div class="section-heading admin-section-heading">
        <div>
          <p class="eyebrow">Archives</p>
          <h2>Sauvegardes disponibles</h2>
        </div>
      </div>
      <table class="admin-table">
        <thead><tr><th>Fichier</th><th>Taille</th><th>Actions</th></tr></thead>
        <tbody>{backup_rows or '<tr><td colspan="3">Aucune sauvegarde créée.</td></tr>'}</tbody>
      </table>
    </section>
    <section class="maintenance-section">
      <div class="section-heading admin-section-heading">
        <div>
          <p class="eyebrow">Audit</p>
          <h2>Actions administrateur</h2>
        </div>
      </div>
      <table class="admin-table admin-audit-table">
        <thead><tr><th>Date</th><th>Compte</th><th>Action</th><th>Cible</th></tr></thead>
        <tbody>{admin_log_rows or '<tr><td colspan="4">Aucune action enregistrée.</td></tr>'}</tbody>
      </table>
    </section>
    <section class="maintenance-section">
      <div class="section-heading admin-section-heading">
        <div>
          <p class="eyebrow">Logs</p>
          <h2>Dernières lignes</h2>
        </div>
      </div>
      <pre class="log-viewer">{log_lines}</pre>
    </section>
    """
    return admin_shell("Maintenance", content, "/admin/maintenance")


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
    try:
        with connect() as conn:
            christmas = conn.execute(
                "SELECT MAX(updated_at) AS updated_at FROM christmas_calendars WHERE published = 1"
            ).fetchone()
    except sqlite3.Error:
        christmas = None
    if christmas_public_window() and christmas and christmas["updated_at"]:
        entries.insert(
            4,
            sitemap_entry("/noel", settings, christmas["updated_at"], "daily", "0.8"),
        )
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


class VertTigeHandler(BaseHTTPRequestHandler):
    server_version = "VertTige/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = self.clean_path(parsed.path)
        query = parse_qs(parsed.query)

        if path == "/favicon.ico":
            self.serve_static("/static/favicon.ico")
            return

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
        elif path == "/recherche":
            self.respond_html(search_page(query))
        elif path == "/articles":
            self.respond_html(articles_page(query))
        elif path.startswith("/articles/"):
            content = article_page(unquote(path.removeprefix("/articles/")))
            if content is None:
                self.respond_html(not_found_page(), status=404)
            else:
                self.respond_html(content)
        elif path == "/galerie":
            self.respond_html(gallery_page(query))
        elif path == "/noel":
            content = christmas_calendar_page(int_or_none(query.get("annee", [""])[0]))
            if content is None:
                self.respond_html(not_found_page(), status=404)
            else:
                self.respond_html(content)
        elif path == "/infos-pratiques":
            self.respond_html(practical_info_page())
        elif path == "/contact":
            self.respond_html(
                contact_page(
                    sent=query.get("sent") == ["1"],
                    saved=query.get("saved") == ["1"],
                    error=query.get("error", [""])[0],
                )
            )
        elif path == "/mentions-legales":
            self.respond_html(legal_page())
        elif path == "/conditions-generales-utilisation":
            self.respond_html(terms_page())
        elif path == "/admin/login":
            self.respond_html(login_page(error=query.get("error") == ["1"]))
        elif path == "/admin/logout":
            user = self.current_user()
            if user:
                self.record_admin_action(user, "Déconnexion", "Session")
            self.clear_session()
        elif path.startswith("/admin"):
            user = self.current_user()
            if not user:
                self.redirect("/admin/login")
                return
            self.route_admin_get(path, user, query)
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

    def route_admin_get(self, path: str, user: sqlite3.Row, query: dict[str, list[str]] | None = None) -> None:
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
        elif path == "/admin/noel":
            self.respond_html(admin_christmas_page(query))
        elif path == "/admin/noel/guide":
            self.respond_html(admin_christmas_guide_page())
        elif match := re.fullmatch(r"/admin/noel/(\d+)/preview", path):
            content = admin_christmas_preview_page(int(match.group(1)), query)
            if content is None:
                self.respond_html(not_found_page(), status=404)
            else:
                self.respond_html(content)
        elif match := re.fullmatch(r"/admin/noel/(\d+)/jours/(\d+)", path):
            self.respond_html(admin_christmas_day_page(int(match.group(1)), int(match.group(2)), query))
        elif match := re.fullmatch(r"/admin/noel/(\d+)", path):
            self.respond_html(admin_christmas_edit_page(int(match.group(1)), query))
        elif path == "/admin/photos":
            self.respond_html(admin_photos_page())
        elif path == "/admin/messages":
            self.respond_html(admin_messages_page())
        elif path == "/admin/users":
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.respond_html(admin_users_page(user))
        elif path == "/admin/maintenance":
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.respond_html(admin_maintenance_page(query))
        elif match := re.fullmatch(r"/admin/maintenance/backups/([^/]+)", path):
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.download_backup(unquote(match.group(1)), user)
        elif path == "/admin/maintenance/logs/server-log.txt":
            if user["role"] != "owner":
                self.redirect("/admin")
                return
            self.download_server_log(user)
        else:
            self.respond_html(not_found_page(), status=404)

    def route_admin_post(self, path: str, user: sqlite3.Row) -> None:
        if admin_action_requires_owner(path) and user["role"] != "owner":
            action, target, _details = admin_action_summary(path)
            self.record_admin_action(
                user,
                "Action refusée",
                target,
                f"Permission référent requise : {action}",
            )
            self.redirect("/admin")
            return
        self.record_admin_action(user, *admin_action_summary(path))
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
        elif path == "/admin/noel/create":
            self.create_christmas_calendar()
        elif match := re.fullmatch(r"/admin/noel/(\d+)/save", path):
            self.save_christmas_calendar(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/noel/(\d+)/delete", path):
            self.delete_christmas_calendar(int(match.group(1)))
        elif match := re.fullmatch(r"/admin/noel/(\d+)/jours/(\d+)", path):
            self.save_christmas_day(int(match.group(1)), int(match.group(2)))
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
            self.create_admin_user()
        elif match := re.fullmatch(r"/admin/users/(\d+)/save", path):
            self.save_admin_user(int(match.group(1)), user)
        elif match := re.fullmatch(r"/admin/users/(\d+)/password", path):
            self.change_admin_password(int(match.group(1)))
        elif path == "/admin/maintenance/backups/create":
            self.create_backup(user)
        elif match := re.fullmatch(r"/admin/maintenance/backups/([^/]+)/delete", path):
            self.delete_backup(unquote(match.group(1)), user)
        else:
            self.respond_html(not_found_page(), status=404)

    def record_admin_action(
        self,
        user: sqlite3.Row,
        action: str,
        target: str = "",
        details: str = "",
    ) -> None:
        insert_admin_activity(
            username=user["username"],
            action=action,
            target=target,
            details=details,
            ip_address=self.client_address[0] if self.client_address else "",
            user_id=user["id"],
        )

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
        logo_url = DEFAULT_SETTINGS["logo_url"] if remove_logo else current_logo
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
        allowed = ["contact_email"]
        contact_email = form.get("contact_email", "").strip()
        if contact_email and not valid_email(contact_email):
            self.redirect("/admin/messages")
            return
        with connect() as conn:
            for key in allowed:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, form.get(key, "").strip()),
                )
        self.redirect("/admin/messages")

    def save_event(self, event_id: int | None = None) -> None:
        form, files = self.read_form()
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
        with connect() as conn:
            image_url = form.get("current_image_url", "").strip()
            image_choice = form.get("event_image_choice", "").strip()
            if image_choice == "__none__":
                image_url = ""
            elif image_choice:
                image_url = existing_photo_upload_url(image_choice) or image_url
            upload = files.get("event_image")
            if upload and upload.data:
                try:
                    uploaded_url = save_photo_upload(
                        conn,
                        upload,
                        title=f"Affiche programmation : {title}",
                        caption=form.get("description", "").strip(),
                        visibility="both",
                    )
                except ValueError:
                    uploaded_url = None
                if uploaded_url:
                    image_url = uploaded_url
            values = (
                title,
                starts_on,
                ends_on,
                start_time,
                end_time,
                form.get("location", "").strip(),
                form.get("address", "").strip(),
                image_url,
                form.get("description", "").strip(),
            )
            if event_id is None:
                conn.execute(
                    """
                    INSERT INTO events
                        (title, starts_on, ends_on, start_time, end_time, location, address, image_url, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (*values, now_iso()),
                )
            else:
                conn.execute(
                    """
                    UPDATE events
                    SET title = ?, starts_on = ?, ends_on = ?, start_time = ?, end_time = ?,
                        location = ?, address = ?, image_url = ?, description = ?
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

    def create_christmas_calendar(self) -> None:
        form, _ = self.read_form()
        year = int_or_none(form.get("year"))
        source_calendar_id = int_or_none(form.get("source_calendar_id"))
        if year is None or year < 2020 or year > 2100:
            self.redirect("/admin/noel?status=invalid")
            return
        with connect() as conn:
            if conn.execute(
                "SELECT id FROM christmas_calendars WHERE year = ?", (year,)
            ).fetchone():
                self.redirect("/admin/noel?status=exists")
                return
            source = None
            if source_calendar_id is not None:
                source = conn.execute(
                    "SELECT * FROM christmas_calendars WHERE id = ?", (source_calendar_id,)
                ).fetchone()
            created = now_iso()
            if source is not None:
                values = (
                    year,
                    source["eyebrow"],
                    source["title"],
                    source["intro"],
                    source["image_url"],
                    source["accent_color"],
                    normalize_christmas_layout_variant(source["layout_variant"]) % 12 + 1,
                    1 if source["show_in_nav"] else 0,
                    1 if source["completion_enabled"] else 0,
                    source["completion_title"],
                    source["completion_message"],
                    source["completion_link_label"],
                    source["completion_link_url"],
                    created,
                    created,
                )
            else:
                values = (
                    year,
                    "24 jours de découvertes",
                    "Le calendrier de l’Avent du jardin",
                    "Chaque jour, une partie de l’image se dévoile avec une idée à cuisiner, jardiner ou partager.",
                    CHRISTMAS_DEFAULT_IMAGE,
                    CHRISTMAS_ACCENT_DEFAULT,
                    (year % 12) + 1,
                    1,
                    1,
                    CHRISTMAS_COMPLETION_TITLE_DEFAULT,
                    CHRISTMAS_COMPLETION_MESSAGE_DEFAULT,
                    CHRISTMAS_COMPLETION_LINK_LABEL_DEFAULT,
                    "",
                    created,
                    created,
                )
            cursor = conn.execute(
                """
                INSERT INTO christmas_calendars
                    (year, eyebrow, title, intro, image_url, accent_color, layout_variant,
                     published, show_in_nav, completion_enabled, completion_title,
                     completion_message, completion_link_label, completion_link_url,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            populate_christmas_days(
                conn,
                cursor.lastrowid,
                source["id"] if source is not None else None,
            )
        status = "duplicate" if source is not None else "created"
        self.redirect(f"/admin/noel/{cursor.lastrowid}?status={status}")

    def save_christmas_calendar(self, calendar_id: int) -> None:
        form, files = self.read_form()
        title = form.get("title", "").strip()
        if not title:
            self.redirect(f"/admin/noel/{calendar_id}")
            return
        with connect() as conn:
            calendar = conn.execute(
                "SELECT * FROM christmas_calendars WHERE id = ?", (calendar_id,)
            ).fetchone()
            if calendar is None:
                self.redirect("/admin/noel")
                return
            image_url = calendar["image_url"] or CHRISTMAS_DEFAULT_IMAGE
            image_choice = form.get("image_choice", "").strip()
            if image_choice == "__none__":
                image_url = CHRISTMAS_DEFAULT_IMAGE
            elif image_choice:
                image_url = existing_photo_upload_url(image_choice) or image_url
            upload = files.get("christmas_image")
            if upload and upload.data:
                try:
                    uploaded_url = save_photo_upload(
                        conn,
                        upload,
                        title=f"Image mystère Noël {calendar['year']}",
                        caption=title,
                        visibility="library",
                    )
                except ValueError:
                    uploaded_url = None
                if uploaded_url:
                    image_url = uploaded_url
            conn.execute(
                """
                UPDATE christmas_calendars
                SET eyebrow = ?, title = ?, intro = ?, image_url = ?, accent_color = ?, layout_variant = ?,
                    published = ?, show_in_nav = ?, completion_enabled = ?, completion_title = ?,
                    completion_message = ?, completion_link_label = ?, completion_link_url = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    form.get("eyebrow", "").strip(),
                    title,
                    form.get("intro", "").strip(),
                    image_url,
                    normalize_hex_color(form.get("accent_color")),
                    normalize_christmas_layout_variant(form.get("layout_variant")),
                    1 if form.get("published") == "1" else 0,
                    1 if form.get("show_in_nav") == "1" else 0,
                    1 if form.get("completion_enabled") == "1" else 0,
                    form.get("completion_title", "").strip()
                    or CHRISTMAS_COMPLETION_TITLE_DEFAULT,
                    form.get("completion_message", "").strip()
                    or CHRISTMAS_COMPLETION_MESSAGE_DEFAULT,
                    form.get("completion_link_label", "").strip()
                    or CHRISTMAS_COMPLETION_LINK_LABEL_DEFAULT,
                    form.get("completion_link_url", "").strip()
                    if valid_optional_url(form.get("completion_link_url", "").strip())
                    else "",
                    now_iso(),
                    calendar_id,
                ),
            )
        self.redirect(f"/admin/noel/{calendar_id}?status=saved")

    def save_christmas_day(self, calendar_id: int, day_number: int) -> None:
        if day_number < 1 or day_number > 24:
            self.redirect(f"/admin/noel/{calendar_id}")
            return
        form, files = self.read_form()
        title = form.get("title", "").strip()
        body = form.get("body", "").strip()
        link_url = form.get("link_url", "").strip()
        if not title or not body or not valid_optional_url(link_url):
            self.redirect(f"/admin/noel/{calendar_id}/jours/{day_number}")
            return
        with connect() as conn:
            calendar = conn.execute(
                "SELECT * FROM christmas_calendars WHERE id = ?", (calendar_id,)
            ).fetchone()
            row = conn.execute(
                "SELECT * FROM christmas_days WHERE calendar_id = ? AND day_number = ?",
                (calendar_id, day_number),
            ).fetchone()
            if calendar is None or row is None:
                self.redirect("/admin/noel")
                return
            image_url = row["image_url"] or ""
            image_choice = form.get("image_choice", "").strip()
            if image_choice == "__none__":
                image_url = ""
            elif image_choice:
                image_url = existing_photo_upload_url(image_choice) or image_url
            upload = files.get("day_image")
            if upload and upload.data:
                try:
                    uploaded_url = save_photo_upload(
                        conn,
                        upload,
                        title=f"Noël {calendar['year']} · jour {day_number}",
                        caption=title,
                        visibility="library",
                    )
                except ValueError:
                    uploaded_url = None
                if uploaded_url:
                    image_url = uploaded_url
            conn.execute(
                """
                UPDATE christmas_days
                SET category = ?, title = ?, teaser = ?, body = ?, image_url = ?,
                    link_url = ?, link_label = ?, enabled = ?, updated_at = ?
                WHERE calendar_id = ? AND day_number = ?
                """,
                (
                    normalize_christmas_category(form.get("category")),
                    title,
                    form.get("teaser", "").strip(),
                    body,
                    image_url,
                    link_url,
                    form.get("link_label", "").strip(),
                    1 if form.get("enabled") == "1" else 0,
                    now_iso(),
                    calendar_id,
                    day_number,
                ),
            )
            conn.execute(
                "UPDATE christmas_calendars SET updated_at = ? WHERE id = ?",
                (now_iso(), calendar_id),
            )
        self.redirect(f"/admin/noel/{calendar_id}/jours/{day_number}?status=saved")

    def delete_christmas_calendar(self, calendar_id: int) -> None:
        with connect() as conn:
            conn.execute("DELETE FROM christmas_days WHERE calendar_id = ?", (calendar_id,))
            conn.execute("DELETE FROM christmas_calendars WHERE id = ?", (calendar_id,))
        self.redirect("/admin/noel?status=deleted")

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
            self.redirect("/contact?error=validation")
            return
        if form.get("website", "").strip():
            self.redirect("/contact?error=captcha")
            return
        if not verify_captcha_answer(form.get("captcha_answer"), form.get("captcha_token")):
            self.redirect("/contact?error=captcha")
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
        self.redirect("/contact?saved=1")

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
            insert_admin_activity(
                username=user["username"],
                action="Connexion à l’administration",
                target="Session",
                ip_address=self.client_address[0] if self.client_address else "",
                user_id=user["id"],
            )
            write_log(f"Connexion admin réussie : {username}")
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
        insert_admin_activity(
            username=username or "identifiant vide",
            action="Connexion refusée",
            target="Session",
            details="Identifiant ou mot de passe incorrect",
            ip_address=self.client_address[0] if self.client_address else "",
        )
        write_log(f"Connexion admin refusée : {username or 'identifiant vide'}")
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
                conn.execute(
                    "UPDATE events SET image_url = '' WHERE image_url = ?",
                    (f"/static/uploads/{row['filename']}",),
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

    def create_backup(self, user: sqlite3.Row) -> None:
        try:
            archive_path = create_backup_archive()
        except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
            write_log(f"Erreur sauvegarde par {user['username']} : {exc}")
            self.redirect("/admin/maintenance?status=backup-error")
            return
        write_log(f"Sauvegarde demandée par {user['username']} : {archive_path.name}")
        self.redirect("/admin/maintenance?status=backup-created")

    def delete_backup(self, filename: str, user: sqlite3.Row) -> None:
        backup_path = backup_path_from_name(filename)
        if not backup_path or not backup_path.exists():
            self.redirect("/admin/maintenance?status=delete-error")
            return
        try:
            backup_path.unlink()
        except OSError as exc:
            write_log(f"Erreur suppression sauvegarde par {user['username']} : {filename} - {exc}")
            self.redirect("/admin/maintenance?status=delete-error")
            return
        write_log(f"Sauvegarde supprimée par {user['username']} : {filename}")
        self.redirect("/admin/maintenance?status=backup-deleted")

    def download_backup(self, filename: str, user: sqlite3.Row) -> None:
        backup_path = backup_path_from_name(filename)
        if not backup_path or not backup_path.exists():
            self.respond_html(not_found_page(), status=404)
            return
        self.record_admin_action(user, "Téléchargement d’une sauvegarde", "Maintenance", filename)
        write_log(f"Sauvegarde téléchargée par {user['username']} : {filename}")
        self.respond_file(
            backup_path,
            filename,
            "application/zip",
        )

    def download_server_log(self, user: sqlite3.Row) -> None:
        if not LOG_PATH.exists():
            self.respond_text("Aucun journal disponible.\n", content_type="text/plain; charset=utf-8")
            return
        self.record_admin_action(user, "Téléchargement du journal serveur", "Maintenance")
        write_log(f"Journal serveur téléchargé par {user['username']}")
        self.respond_file(LOG_PATH, "vert-tige-server.log", "text/plain; charset=utf-8")

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
            f"style-src 'self' 'nonce-{nonce}'; form-action 'self'",
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

    def respond_file(self, path: Path, filename: str, content_type: str) -> None:
        data = path.read_bytes()
        quoted_name = quote(filename)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted_name}")
        self.send_header("Cache-Control", "no-store")
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
