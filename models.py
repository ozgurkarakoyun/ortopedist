"""
Veritabanı modelleri.
Çoklu dil yapısı: Post + PostTranslation (bir yazı, birden çok dilde içerik).
"""
from datetime import datetime
from flask_login import UserMixin
import bcrypt
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="admin")  # admin, editor
    is_active_user = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), self.password_hash.encode("utf-8")
            )
        except Exception:
            return False


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name_tr = db.Column(db.String(100), nullable=False)
    name_en = db.Column(db.String(100))
    name_ar = db.Column(db.String(100))

    def name(self, lang: str = "tr") -> str:
        return getattr(self, f"name_{lang}", None) or self.name_tr


class Post(db.Model):
    """Bir yazı, dilden bağımsız meta verileri tutar."""
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(255), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), default="draft", index=True)  # draft, published, archived
    featured_image = db.Column(db.String(500))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Yapay zeka meta verisi
    ai_generated = db.Column(db.Boolean, default=False)
    source_topic = db.Column(db.String(500))  # Hangi konu önerisinden üretildi
    original_url = db.Column(db.String(500))  # Migrasyon kaynak URL'si

    # Tarihler
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # İlişkiler
    category = db.relationship("Category", backref="posts")
    author = db.relationship("User", backref="posts")
    translations = db.relationship(
        "PostTranslation",
        backref="post",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def get_translation(self, lang: str = "tr"):
        """Belirtilen dildeki çeviriyi döndürür, yoksa TR'yi fallback yapar."""
        for t in self.translations:
            if t.language == lang and t.is_published:
                return t
        # Fallback: Türkçe
        for t in self.translations:
            if t.language == "tr":
                return t
        return self.translations[0] if self.translations else None

    def has_translation(self, lang: str) -> bool:
        return any(t.language == lang for t in self.translations)

    def is_published(self, lang: str = "tr") -> bool:
        if self.status != "published":
            return False
        t = next((t for t in self.translations if t.language == lang), None)
        return t.is_published if t else False


class PostTranslation(db.Model):
    """Bir yazının belirli bir dildeki içeriği."""
    __tablename__ = "post_translations"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False, index=True)
    language = db.Column(db.String(5), nullable=False, index=True)  # tr, en, ar

    title = db.Column(db.String(500), nullable=False)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)  # Markdown

    # SEO
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.String(500))
    meta_keywords = db.Column(db.String(500))

    # Çeviri durumu (taslak/onaylı)
    is_published = db.Column(db.Boolean, default=False)
    is_ai_translated = db.Column(db.Boolean, default=False)
    ai_review_pending = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("post_id", "language", name="uix_post_lang"),
    )


class TopicSuggestion(db.Model):
    """Yapay zekanın önerdiği yazı konuları."""
    __tablename__ = "topic_suggestions"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    relevance_score = db.Column(db.Float, default=0.5)
    sources = db.Column(db.Text)  # JSON: kaynak URL listesi
    keywords = db.Column(db.String(500))

    status = db.Column(db.String(20), default="new", index=True)  # new, used, dismissed
    used_post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class AILog(db.Model):
    """AI çağrılarının kayıt günlüğü (kota ve hata takibi)."""
    __tablename__ = "ai_logs"

    id = db.Column(db.Integer, primary_key=True)
    operation = db.Column(db.String(50))  # write, translate, enhance, seo, topics
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    success = db.Column(db.Boolean, default=True)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
