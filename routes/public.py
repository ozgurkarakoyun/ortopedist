"""
Public-facing routes.
URL yapısı:
  /                -> Türkçe ana sayfa
  /en/             -> English homepage
  /ar/             -> Arabic homepage
  /yazi/<slug>     -> TR yazı
  /en/post/<slug>  -> EN yazı
  /ar/post/<slug>  -> AR yazı
"""
from datetime import datetime
from flask import Blueprint, render_template, abort, request, redirect, url_for, session
from sqlalchemy import or_
import markdown as md

from extensions import db
from models import Post, PostTranslation, Category

public_bp = Blueprint("public", __name__)


# --- Yardımcılar -----------------------------------------------------------

def render_markdown(text: str) -> str:
    """Markdown -> sterilize edilmiş HTML."""
    if not text:
        return ""
    html = md.markdown(
        text,
        extensions=["extra", "sane_lists", "smarty", "toc", "tables", "nl2br"],
    )
    # Bleach ile sterilize edebilirsiniz; içerik yazarın olduğu için pas geçiyoruz
    return html


def published_posts_for(lang: str):
    """Belirtilen dilde yayınlanmış yazıları getiren temel sorgu."""
    return (
        db.session.query(Post)
        .join(PostTranslation)
        .filter(
            Post.status == "published",
            PostTranslation.language == lang,
            PostTranslation.is_published == True,  # noqa: E712
        )
        .order_by(Post.published_at.desc().nullslast())
    )


def _set_lang(lang):
    session["lang"] = lang


# --- Ana sayfa -------------------------------------------------------------

@public_bp.route("/")
def index():
    _set_lang("tr")
    return _render_index("tr")


@public_bp.route("/en/")
def index_en():
    _set_lang("en")
    return _render_index("en")


@public_bp.route("/ar/")
def index_ar():
    _set_lang("ar")
    return _render_index("ar")


def _render_index(lang):
    page = request.args.get("page", 1, type=int)
    pagination = published_posts_for(lang).paginate(
        page=page, per_page=9, error_out=False
    )
    return render_template(
        "public/index.html",
        pagination=pagination,
        posts=pagination.items,
        lang=lang,
    )


# --- Tek yazı --------------------------------------------------------------

@public_bp.route("/yazi/<slug>")
def post_tr(slug):
    _set_lang("tr")
    return _render_post(slug, "tr")


@public_bp.route("/en/post/<slug>")
def post_en(slug):
    _set_lang("en")
    return _render_post(slug, "en")


@public_bp.route("/ar/post/<slug>")
def post_ar(slug):
    _set_lang("ar")
    return _render_post(slug, "ar")


def _render_post(slug, lang):
    post = db.session.query(Post).filter_by(slug=slug, status="published").first()
    if not post:
        abort(404)
    translation = post.get_translation(lang)
    if not translation or not translation.is_published:
        # Bu dilde yayınlanmamışsa, mevcut dillere yönlendir veya 404
        for alt in ("tr", "en", "ar"):
            t = next((t for t in post.translations if t.language == alt and t.is_published), None)
            if t:
                target = {"tr": "public.post_tr", "en": "public.post_en", "ar": "public.post_ar"}[alt]
                return redirect(url_for(target, slug=slug))
        abort(404)

    content_html = render_markdown(translation.content)

    # İlgili yazılar (aynı kategori, son 3)
    related = []
    if post.category_id:
        related = (
            published_posts_for(lang)
            .filter(Post.category_id == post.category_id, Post.id != post.id)
            .limit(3)
            .all()
        )

    return render_template(
        "public/post.html",
        post=post,
        translation=translation,
        content_html=content_html,
        related=related,
        lang=lang,
    )


# --- Kategori --------------------------------------------------------------

@public_bp.route("/kategori/<slug>")
@public_bp.route("/<lang>/category/<slug>")
def category(slug, lang="tr"):
    if lang not in ("tr", "en", "ar"):
        lang = "tr"
    _set_lang(lang)
    cat = db.session.query(Category).filter_by(slug=slug).first()
    if not cat:
        abort(404)
    page = request.args.get("page", 1, type=int)
    pagination = (
        published_posts_for(lang)
        .filter(Post.category_id == cat.id)
        .paginate(page=page, per_page=9, error_out=False)
    )
    return render_template(
        "public/index.html",
        pagination=pagination,
        posts=pagination.items,
        lang=lang,
        category=cat,
    )


# --- Arama -----------------------------------------------------------------

@public_bp.route("/ara")
@public_bp.route("/<lang>/search")
def search(lang="tr"):
    if lang not in ("tr", "en", "ar"):
        lang = "tr"
    _set_lang(lang)
    q = (request.args.get("q") or "").strip()
    results = []
    if q and len(q) >= 2:
        results = (
            published_posts_for(lang)
            .filter(
                or_(
                    PostTranslation.title.ilike(f"%{q}%"),
                    PostTranslation.content.ilike(f"%{q}%"),
                    PostTranslation.excerpt.ilike(f"%{q}%"),
                )
            )
            .limit(50)
            .all()
        )
    return render_template("public/search.html", q=q, results=results, lang=lang)


# --- Hakkımda / İletişim ---------------------------------------------------

@public_bp.route("/hakkimda")
@public_bp.route("/<lang>/about")
def about(lang="tr"):
    if lang not in ("tr", "en", "ar"):
        lang = "tr"
    _set_lang(lang)
    return render_template("public/about.html", lang=lang)


@public_bp.route("/iletisim")
@public_bp.route("/<lang>/contact")
def contact(lang="tr"):
    if lang not in ("tr", "en", "ar"):
        lang = "tr"
    _set_lang(lang)
    return render_template("public/contact.html", lang=lang)


# --- SEO: sitemap & robots -------------------------------------------------

@public_bp.route("/sitemap.xml")
def sitemap():
    from flask import Response, current_app

    base = current_app.config["SITE_URL"]
    urls = [(base + "/", datetime.utcnow())]
    for lang in ("en", "ar"):
        urls.append((f"{base}/{lang}/", datetime.utcnow()))

    posts = (
        db.session.query(Post, PostTranslation)
        .join(PostTranslation)
        .filter(Post.status == "published", PostTranslation.is_published == True)  # noqa: E712
        .all()
    )
    for post, t in posts:
        if t.language == "tr":
            url = f"{base}/yazi/{post.slug}"
        else:
            url = f"{base}/{t.language}/post/{post.slug}"
        urls.append((url, post.updated_at))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for u, d in urls:
        xml.append(
            f"<url><loc>{u}</loc><lastmod>{d.strftime('%Y-%m-%d')}</lastmod></url>"
        )
    xml.append("</urlset>")
    return Response("\n".join(xml), mimetype="application/xml")


@public_bp.route("/robots.txt")
def robots():
    from flask import Response, current_app
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /api\n"
        f"Sitemap: {current_app.config['SITE_URL']}/sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


# --- RSS -------------------------------------------------------------------

@public_bp.route("/feed.xml")
@public_bp.route("/<lang>/feed.xml")
def feed(lang="tr"):
    from flask import Response, current_app
    if lang not in ("tr", "en", "ar"):
        lang = "tr"
    posts = published_posts_for(lang).limit(20).all()
    base = current_app.config["SITE_URL"]
    items = []
    for p in posts:
        t = p.get_translation(lang)
        if not t:
            continue
        if lang == "tr":
            url = f"{base}/yazi/{p.slug}"
        else:
            url = f"{base}/{lang}/post/{p.slug}"
        items.append(f"""
<item>
<title>{t.title}</title>
<link>{url}</link>
<guid>{url}</guid>
<pubDate>{(p.published_at or p.created_at).strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
<description><![CDATA[{t.excerpt or ''}]]></description>
</item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{current_app.config['SITE_NAME']}</title>
<link>{base}</link>
<description>Ortopedi ve Travmatoloji Blog</description>
{''.join(items)}
</channel></rss>"""
    return Response(rss, mimetype="application/rss+xml")
