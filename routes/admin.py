"""
Admin panel routes.
- /admin/login
- /admin/                  -> Dashboard
- /admin/posts             -> Yazı listesi
- /admin/posts/new         -> Yeni yazı
- /admin/posts/<id>/edit   -> Düzenleme
- /admin/topics            -> AI konu önerileri
- /admin/translations/<id> -> Çeviri yönetimi
"""
from datetime import datetime
import json
import os

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash,
    abort, current_app, jsonify
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from slugify import slugify

from extensions import db, limiter
from models import Post, PostTranslation, User, Category, TopicSuggestion, AILog

admin_bp = Blueprint("admin", __name__)


# --- Yardımcılar -----------------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


# --- Auth ------------------------------------------------------------------

@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = db.session.query(User).filter_by(email=email).first()
        if user and user.is_active_user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("admin.dashboard"))
        flash("E-posta veya şifre hatalı.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


# --- Dashboard -------------------------------------------------------------

@admin_bp.route("/")
@login_required
def dashboard():
    stats = {
        "total_posts": db.session.query(Post).count(),
        "published": db.session.query(Post).filter_by(status="published").count(),
        "drafts": db.session.query(Post).filter_by(status="draft").count(),
        "topics_pending": db.session.query(TopicSuggestion).filter_by(status="new").count(),
        "translations_pending": db.session.query(PostTranslation).filter_by(ai_review_pending=True).count(),
    }
    recent_posts = (
        db.session.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    )
    pending_translations = (
        db.session.query(PostTranslation)
        .filter_by(ai_review_pending=True)
        .order_by(PostTranslation.updated_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_posts=recent_posts,
        pending_translations=pending_translations,
    )


# --- Posts -----------------------------------------------------------------

@admin_bp.route("/posts")
@login_required
def posts_list():
    status = request.args.get("status", "all")
    q = db.session.query(Post)
    if status in ("draft", "published", "archived"):
        q = q.filter(Post.status == status)
    posts = q.order_by(Post.created_at.desc()).all()
    return render_template("admin/posts_list.html", posts=posts, status=status)


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@login_required
def post_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        category_id = request.form.get("category_id") or None
        slug = request.form.get("slug", "").strip() or slugify(title)

        if not title or not content:
            flash("Başlık ve içerik zorunlu.", "error")
            return redirect(url_for("admin.post_new"))

        # Slug benzersizliği
        base_slug = slug
        i = 1
        while db.session.query(Post).filter_by(slug=slug).first():
            slug = f"{base_slug}-{i}"
            i += 1

        post = Post(
            slug=slug,
            status="draft",
            category_id=int(category_id) if category_id else None,
            author_id=current_user.id,
        )
        db.session.add(post)
        db.session.flush()

        translation = PostTranslation(
            post_id=post.id,
            language="tr",
            title=title,
            excerpt=excerpt,
            content=content,
            is_published=False,
        )
        db.session.add(translation)
        db.session.commit()

        flash("Yazı taslak olarak kaydedildi.", "success")
        return redirect(url_for("admin.post_edit", post_id=post.id))

    categories = db.session.query(Category).all()
    return render_template("admin/post_editor.html", post=None, translation=None, categories=categories, lang="tr")


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def post_edit(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    lang = request.args.get("lang", "tr")
    if lang not in ("tr", "en", "ar"):
        lang = "tr"

    translation = next((t for t in post.translations if t.language == lang), None)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        excerpt = request.form.get("excerpt", "").strip()
        meta_title = request.form.get("meta_title", "").strip()
        meta_description = request.form.get("meta_description", "").strip()
        meta_keywords = request.form.get("meta_keywords", "").strip()
        slug = request.form.get("slug", "").strip()
        category_id = request.form.get("category_id") or None
        featured_image = request.form.get("featured_image", "").strip()
        status = request.form.get("status", "draft")
        publish_translation = request.form.get("publish_translation") == "on"

        if not translation:
            translation = PostTranslation(post_id=post.id, language=lang, title=title, content=content)
            db.session.add(translation)

        translation.title = title
        translation.content = content
        translation.excerpt = excerpt
        translation.meta_title = meta_title
        translation.meta_description = meta_description
        translation.meta_keywords = meta_keywords
        translation.is_published = publish_translation
        if publish_translation:
            translation.ai_review_pending = False

        if slug and slug != post.slug:
            # Slug değişikliği için benzersizlik kontrolü
            if not db.session.query(Post).filter(Post.slug == slug, Post.id != post.id).first():
                post.slug = slug
        if category_id:
            post.category_id = int(category_id)
        if featured_image:
            post.featured_image = featured_image
        post.status = status
        if status == "published" and not post.published_at:
            post.published_at = datetime.utcnow()

        db.session.commit()
        flash("Yazı güncellendi.", "success")
        return redirect(url_for("admin.post_edit", post_id=post.id, lang=lang))

    categories = db.session.query(Category).all()
    return render_template(
        "admin/post_editor.html",
        post=post,
        translation=translation,
        categories=categories,
        lang=lang,
    )


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def post_delete(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    db.session.delete(post)
    db.session.commit()
    flash("Yazı silindi.", "success")
    return redirect(url_for("admin.posts_list"))


# --- AI: Topics ------------------------------------------------------------

@admin_bp.route("/topics")
@login_required
def topics():
    status = request.args.get("status", "new")
    q = db.session.query(TopicSuggestion)
    if status in ("new", "used", "dismissed"):
        q = q.filter(TopicSuggestion.status == status)
    items = q.order_by(TopicSuggestion.created_at.desc()).all()
    return render_template("admin/topics.html", topics=items, status=status)


@admin_bp.route("/topics/<int:topic_id>/dismiss", methods=["POST"])
@login_required
def topic_dismiss(topic_id):
    t = db.session.get(TopicSuggestion, topic_id) or abort(404)
    t.status = "dismissed"
    db.session.commit()
    return redirect(url_for("admin.topics"))


# --- Görsel Yükleme --------------------------------------------------------

@admin_bp.route("/uploads", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Dosya yok"}), 400
    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename):
        return jsonify({"error": "Geçersiz dosya türü"}), 400
    fname = secure_filename(f.filename)
    fname = f"{int(datetime.utcnow().timestamp())}_{fname}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
    f.save(path)
    url = url_for("static", filename=f"images/uploads/{fname}", _external=False)
    return jsonify({"url": url})


# --- Çeviri yönetimi -------------------------------------------------------

@admin_bp.route("/translations")
@login_required
def translations():
    """AI tarafından çevrilmiş ama henüz onaylanmamış yazılar."""
    pending = (
        db.session.query(PostTranslation)
        .filter_by(ai_review_pending=True)
        .order_by(PostTranslation.updated_at.desc())
        .all()
    )
    return render_template("admin/translations.html", pending=pending)
