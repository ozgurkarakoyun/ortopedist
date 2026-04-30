"""
Yapılandırma dosyası
Çevre değişkenleri Railway'de tanımlanır, lokalde .env dosyası kullanılır.
"""
import os
from pathlib import Path

basedir = Path(__file__).resolve().parent


class Config:
    # Genel
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-degistir-bunu-mutlaka")
    SITE_NAME = os.environ.get("SITE_NAME", "Ortopedist")
    SITE_URL = os.environ.get("SITE_URL", "https://ortopedist.blog")
    AUTHOR_NAME = os.environ.get("AUTHOR_NAME", "Doç. Dr. Özgür Karakoyun")

    # Veritabanı
    # Railway PostgreSQL ekleyince DATABASE_URL otomatik gelir.
    db_url = os.environ.get("DATABASE_URL", f"sqlite:///{basedir / 'app.db'}")
    # Railway 'postgres://' verir, SQLAlchemy 'postgresql://' bekler:
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # i18n
    LANGUAGES = {"tr": "Türkçe", "en": "English", "ar": "العربية"}
    BABEL_DEFAULT_LOCALE = "tr"
    BABEL_DEFAULT_TIMEZONE = "Europe/Istanbul"

    # Yükleme
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    UPLOAD_FOLDER = str(basedir / "static" / "images" / "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

    # Anthropic API
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-5")

    # OpenAI (görsel üretimi için)
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-1")
    IMAGE_QUALITY = os.environ.get("IMAGE_QUALITY", "medium")  # low | medium | high

    # Admin
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@ortopedist.blog")

    # Güvenlik
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    WTF_CSRF_TIME_LIMIT = 3600

    # Sayfalama
    POSTS_PER_PAGE = 9
