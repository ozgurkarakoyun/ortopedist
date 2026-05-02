"""
Admin panel routes.
- /admin/login
- /admin/                  -> Dashboard
- /admin/posts             -> Yazı listesi
- /admin/posts/new         -> Yeni yazı
- /admin/posts/<id>/edit   -> Düzenleme
- /admin/topics            -> AI konu önerileri
- /admin/translations/<id> -> Çeviri yönetimi
- /admin/bootstrap         -> İlk admin oluşturma (BOOTSTRAP_KEY env var ile korunur)
"""
from datetime import datetime
import json
import os

from flask import (
    Blueprint, render_template, redirect, url_for, request, flash,
    abort, current_app, jsonify, render_template_string
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from slugify import slugify

from extensions import db, limiter, csrf
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


# --- WordPress İçerik Migrasyonu (tek tık) --------------------------------

@admin_bp.route("/migrate-wp", methods=["GET"])
@login_required
def migrate_wp_page():
    """Migrasyon arayüzü."""
    existing_count = db.session.query(Post).filter(Post.original_url.isnot(None)).count()
    return render_template("admin/migrate.html", existing_count=existing_count)


@admin_bp.route("/migrate-wp/run", methods=["POST"])
@login_required
@limiter.limit("3 per hour")
def migrate_wp_run():
    """
    WordPress'ten içerik aktarımını çalıştırır (synchronous).
    Mevcut migrate_content.py modülünü kullanır.
    """
    import sys
    from pathlib import Path

    # scripts/ klasörünü path'e ekle
    scripts_dir = str(Path(current_app.root_path) / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        import migrate_content
    except ImportError as e:
        return jsonify({"error": f"Migration modülü yüklenemedi: {e}"}), 500

    payload = request.get_json(silent=True) or {}
    source = payload.get("source", "https://ortopedist.blog")
    limit = int(payload.get("limit", 0))
    dry_run = bool(payload.get("dry_run", False))

    try:
        urls = migrate_content.fetch_post_urls(source)
    except Exception as e:
        return jsonify({"error": f"Sitemap/RSS okunamadı: {e}"}), 500

    if limit:
        urls = urls[:limit]

    results = {"total": len(urls), "success": 0, "skipped": 0, "failed": 0, "items": []}

    for url in urls:
        try:
            data = migrate_content.parse_post_page(url)
            existing = db.session.query(Post).filter_by(slug=data["slug"]).first()
            if existing:
                results["skipped"] += 1
                results["items"].append({"url": url, "status": "skipped", "title": data.get("title", "")})
                continue
            if dry_run:
                results["items"].append({"url": url, "status": "preview", "title": data.get("title", "")})
                continue
            post = migrate_content.import_post(data, dry_run=False)
            if post:
                results["success"] += 1
                results["items"].append({"url": url, "status": "imported", "title": data.get("title", "")})
            else:
                results["failed"] += 1
                results["items"].append({"url": url, "status": "failed", "error": "boş içerik"})
        except Exception as e:
            results["failed"] += 1
            results["items"].append({"url": url, "status": "error", "error": str(e)})

    return jsonify(results)


# --- WXR (WordPress Export XML) Import ------------------------------------

@admin_bp.route("/migrate-wp/upload-xml", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def migrate_wp_upload_xml():
    """
    WordPress export XML (WXR) dosyasını yükler, parse eder ve içeri aktarır.
    Bu yöntem scrape'a göre daha güvenilir: tarihler, slug'lar, kategoriler
    aynen orijinal sitedeki gibi gelir.
    """
    if "xml" not in request.files:
        return jsonify({"error": "XML dosyası yüklenmedi"}), 400

    f = request.files["xml"]
    if not f.filename or not f.filename.lower().endswith(".xml"):
        return jsonify({"error": "Dosya .xml uzantılı olmalı"}), 400

    dry_run = request.form.get("dry_run") == "on"

    # Geçici dosyaya kaydet
    import tempfile
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xml")
    f.save(tmp.name)
    tmp.close()

    try:
        from services.wxr_importer import parse_wxr
    except ImportError as e:
        return jsonify({"error": f"WXR importer yüklenemedi: {e}"}), 500

    results = {"total": 0, "success": 0, "skipped": 0, "failed": 0, "items": []}

    try:
        for data in parse_wxr(tmp.name):
            results["total"] += 1
            try:
                # Slug çakışıyorsa atla
                existing = db.session.query(Post).filter_by(slug=data["slug"]).first()
                if existing:
                    results["skipped"] += 1
                    results["items"].append({"status": "skipped", "title": data["title"], "slug": data["slug"]})
                    continue

                if dry_run:
                    results["items"].append({"status": "preview", "title": data["title"], "slug": data["slug"]})
                    continue

                # Kategori (ilk kategoriyi kullan)
                cat_id = None
                if data["categories"]:
                    cat_name = data["categories"][0]
                    if cat_name.lower() not in ("uncategorized", "kategorisiz", ""):
                        cat_slug = slugify(cat_name)
                        cat = db.session.query(Category).filter_by(slug=cat_slug).first()
                        if not cat:
                            cat = Category(slug=cat_slug, name_tr=cat_name)
                            db.session.add(cat)
                            db.session.flush()
                        cat_id = cat.id

                post = Post(
                    slug=data["slug"],
                    status="published",
                    category_id=cat_id,
                    featured_image=data.get("featured_image"),
                    published_at=data["published_at"] or datetime.utcnow(),
                    original_url=data.get("link"),
                    author_id=current_user.id,
                )
                db.session.add(post)
                db.session.flush()

                translation = PostTranslation(
                    post_id=post.id,
                    language="tr",
                    title=data["title"][:500] or "(Başlıksız)",
                    excerpt=(data["excerpt"] or "")[:500] or None,
                    content=data["content"] or "(İçerik boş)",
                    is_published=True,
                )
                db.session.add(translation)
                db.session.commit()

                results["success"] += 1
                results["items"].append({"status": "imported", "title": data["title"], "slug": data["slug"]})

            except Exception as e:
                db.session.rollback()
                results["failed"] += 1
                results["items"].append({"status": "error", "title": data.get("title", "?"), "error": str(e)})

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return jsonify(results)


# --- Bootstrap: İlk Admin Oluşturma ----------------------------------------
# Sadece BOOTSTRAP_KEY env var doğru sağlandığında çalışır.
# Bir admin oluşturulduktan sonra otomatik devre dışı kalır (güvenlik).

@admin_bp.route("/bootstrap", methods=["GET", "POST"])
@csrf.exempt
@limiter.limit("10 per hour")
def bootstrap():
    expected = os.environ.get("BOOTSTRAP_KEY") or current_app.config.get("BOOTSTRAP_KEY")
    if not expected:
        return ("BOOTSTRAP_KEY ortam değişkeni Railway Variables'a eklenmemiş. "
                "Lütfen önce ekleyin (Railway → Variables → BOOTSTRAP_KEY=... ).", 503)

    provided = request.args.get("key") or request.form.get("key", "")
    if provided != expected:
        return ("Geçersiz veya eksik anahtar. URL'ye ?key=... eklediğinizden emin olun.", 403)

    # Zaten admin varsa: kapalı
    if db.session.query(User).filter(User.role == "admin").first():
        return ("Bu sistemde zaten admin tanımlı. Bootstrap endpoint'i devre dışı. "
                "Lütfen mevcut hesapla giriş yapın: /admin/login — "
                "veya Railway shell ile yeni hesap oluşturun.", 403)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip() or "Admin"
        password = request.form.get("password", "")

        if not email or "@" not in email:
            return _bootstrap_form(provided, error="Geçerli bir e-posta gerekli.")
        if len(password) < 8:
            return _bootstrap_form(provided, error="Şifre en az 8 karakter olmalı.")

        try:
            u = User(email=email, name=name, role="admin", is_active_user=True)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return _bootstrap_form(provided, error=f"Hata: {e}")

        return render_template_string("""
<!DOCTYPE html><html><head><meta charset="utf-8"><title>Hazır</title>
<style>body{font-family:sans-serif;max-width:480px;margin:4rem auto;padding:2rem;background:#f5f7fa}
.box{background:white;border-radius:12px;padding:2.5rem;box-shadow:0 2px 12px rgba(0,0,0,.06)}
h1{color:#0d6e70;margin:0 0 1rem} a.btn{display:inline-block;margin-top:1rem;padding:.75rem 1.5rem;
background:#0d6e70;color:white;text-decoration:none;border-radius:6px;font-weight:600}</style></head>
<body><div class="box">
<h1>✓ Admin oluşturuldu</h1>
<p><strong>{{ email }}</strong> hesabıyla giriş yapabilirsiniz.</p>
<p style="color:#dc2626;font-size:.9rem;background:#fee2e2;padding:.75rem;border-radius:6px;margin-top:1rem">
⚠ Güvenlik için Railway Variables'tan <code>BOOTSTRAP_KEY</code> değişkenini şimdi silin.
Bu endpoint zaten otomatik kilitlendi (admin oluştuğu için), ama temiz olsun.</p>
<a href="/admin/login" class="btn">→ Giriş Yap</a>
</div></body></html>
""", email=email)

    return _bootstrap_form(provided)


def _bootstrap_form(key_val, error=None):
    return render_template_string("""
<!DOCTYPE html><html><head><meta charset="utf-8"><title>İlk Admin Oluştur</title>
<style>body{font-family:sans-serif;max-width:440px;margin:4rem auto;padding:2rem;background:#f5f7fa}
.box{background:white;border-radius:12px;padding:2.5rem;box-shadow:0 2px 12px rgba(0,0,0,.06)}
h1{color:#1a2332;margin:0 0 .5rem;font-size:1.5rem}
.muted{color:#5a6473;font-size:.9rem;margin:0 0 1.5rem}
label{display:block;margin-bottom:1rem;font-size:.85rem;font-weight:600;color:#5a6473}
input{width:100%;padding:.625rem .75rem;border:1px solid #e6e8ed;border-radius:6px;
margin-top:.4rem;font-size:1rem;font-family:inherit;box-sizing:border-box}
button{width:100%;padding:.75rem;background:#0d6e70;color:white;border:0;border-radius:6px;
font-weight:600;font-size:1rem;cursor:pointer;margin-top:.5rem}
.err{background:#fee2e2;color:#991b1b;padding:.75rem;border-radius:6px;
font-size:.9rem;margin-bottom:1rem}</style></head>
<body><div class="box">
<h1>İlk Admin Oluştur</h1>
<p class="muted">Bu form, sadece henüz hiç admin tanımlanmamışsa çalışır. Bir admin oluşturulduktan sonra otomatik kilitlenir.</p>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="POST">
<input type="hidden" name="key" value="{{ key }}">
<label>E-posta<input type="email" name="email" required></label>
<label>İsim<input type="text" name="name" placeholder="Özgür Karakoyun"></label>
<label>Şifre <small>(min 8 karakter)</small><input type="password" name="password" required minlength="8"></label>
<button type="submit">Oluştur</button>
</form>
</div></body></html>
""", key=key_val, error=error)


# --- SEO Bakımı: Meta'ları temizle ve doldur -----------------------------

@admin_bp.route("/seo-cleanup")
@login_required
def seo_cleanup_page():
    """Eksik/bozuk meta verilerini gösteren ve toplu düzeltme yapan sayfa."""
    # "None" string'i veya NULL meta_title olan yazılar
    bad_meta_title = db.session.query(PostTranslation).filter(
        db.or_(
            PostTranslation.meta_title.is_(None),
            db.func.lower(PostTranslation.meta_title).in_(["none", "null", ""]),
        )
    ).all()
    bad_excerpt = db.session.query(PostTranslation).filter(
        db.or_(
            PostTranslation.excerpt.is_(None),
            db.func.lower(PostTranslation.excerpt).in_(["none", "null", ""]),
        )
    ).all()
    bad_meta_desc = db.session.query(PostTranslation).filter(
        db.or_(
            PostTranslation.meta_description.is_(None),
            db.func.lower(PostTranslation.meta_description).in_(["none", "null", ""]),
        )
    ).all()
    return render_template(
        "admin/seo_cleanup.html",
        bad_meta_title=bad_meta_title,
        bad_excerpt=bad_excerpt,
        bad_meta_desc=bad_meta_desc,
    )


@admin_bp.route("/seo-cleanup/normalize", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def seo_cleanup_normalize():
    """'None'/'null' string'lerini gerçek NULL'a çevirir (AI çağırmaz, ücretsiz)."""
    fixed = 0
    bad_values = ["none", "null", "undefined", "nan", ""]
    for t in db.session.query(PostTranslation).all():
        changed = False
        for field in ("meta_title", "meta_description", "excerpt", "meta_keywords"):
            v = getattr(t, field, None)
            if v is None:
                continue
            if str(v).strip().lower() in bad_values:
                setattr(t, field, None)
                changed = True
        if changed:
            fixed += 1
    db.session.commit()
    return jsonify({"ok": True, "fixed": fixed})


@admin_bp.route("/seo-cleanup/missing-list", methods=["GET"])
@login_required
def seo_cleanup_missing_list():
    """Eksik meta'sı olan yazıların ID + başlık listesini döner."""
    missing = db.session.query(PostTranslation).filter(
        PostTranslation.is_published == True,  # noqa: E712
        PostTranslation.language == "tr",
        db.or_(
            PostTranslation.meta_description.is_(None),
            db.func.length(db.func.coalesce(PostTranslation.meta_description, "")) < 50,
            PostTranslation.excerpt.is_(None),
            db.func.length(db.func.coalesce(PostTranslation.excerpt, "")) < 30,
        ),
    ).all()
    return jsonify({
        "total": len(missing),
        "items": [{"id": t.id, "title": t.title[:80]} for t in missing],
    })


@admin_bp.route("/seo-cleanup/fill-one/<int:translation_id>", methods=["POST"])
@login_required
@limiter.limit("100 per hour")
def seo_cleanup_fill_one(translation_id):
    """Tek bir yazının eksik meta'sını AI ile doldurur. JS bunu sırayla çağırır."""
    from services.seo import SEOGenerator

    t = db.session.get(PostTranslation, translation_id)
    if not t:
        return jsonify({"error": "Çeviri bulunamadı"}), 404

    try:
        seo = SEOGenerator(
            api_key=current_app.config["ANTHROPIC_API_KEY"],
            model=current_app.config["AI_MODEL"],
        )
        data = seo.generate(title=t.title, content=t.content or "", lang=t.language)
        updated = []
        if not t.meta_title or len(t.meta_title) < 10:
            t.meta_title = (data.get("meta_title") or "")[:255]
            updated.append("title")
        if not t.meta_description or len(t.meta_description) < 50:
            t.meta_description = (data.get("meta_description") or "")[:500]
            updated.append("desc")
        if not t.excerpt or len(t.excerpt) < 30:
            t.excerpt = (data.get("meta_description") or data.get("structured_summary") or "")[:300]
            updated.append("excerpt")
        if not t.meta_keywords:
            t.meta_keywords = (data.get("meta_keywords") or "")[:500]
            updated.append("keywords")
        db.session.commit()
        return jsonify({"ok": True, "updated": ", ".join(updated) or "(zaten doluydu)"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(f"fill-one error for translation {translation_id}")
        return jsonify({"error": str(e)[:200]}), 500


# Eski endpoint geriye dönük uyumluluk için — kullanılmıyor artık
@admin_bp.route("/seo-cleanup/fill-missing", methods=["POST"])
@login_required
def seo_cleanup_fill_missing_deprecated():
    return jsonify({
        "error": "Bu endpoint kaldırıldı. Yeni JS missing-list + fill-one kullanır.",
    }), 410
