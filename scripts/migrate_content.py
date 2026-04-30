#!/usr/bin/env python3
"""
Mevcut ortopedist.blog WordPress sitesinden içerikleri yeni veritabanına aktarır.

Kullanım:
    python scripts/migrate_content.py
    python scripts/migrate_content.py --limit 5         # Sadece 5 yazı (test)
    python scripts/migrate_content.py --dry-run         # Sadece preview
    python scripts/migrate_content.py --source URL      # Farklı bir kaynak

WordPress 'feed/' (RSS) ve sitemap'i kullanır; HTML'i markdown'a çevirir.
"""
import sys
import os
import argparse
import logging
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Proje köküne path ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedparser
import requests
from bs4 import BeautifulSoup
from slugify import slugify

from app import create_app
from extensions import db
from models import Post, PostTranslation, Category

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate")

DEFAULT_SOURCE = "https://ortopedist.blog"
USER_AGENT = "OrtopedistMigrator/1.0 (+https://ortopedist.blog)"


def fetch_post_urls(base_url: str) -> list:
    """Sitemap veya RSS'ten yazı URL'lerini çıkarır."""
    urls = set()

    # 1. Sitemap dene
    for sm_path in ("/sitemap.xml", "/wp-sitemap.xml", "/sitemap_index.xml"):
        try:
            r = requests.get(base_url + sm_path, timeout=15, headers={"User-Agent": USER_AGENT})
            if r.status_code == 200 and "<loc>" in r.text:
                soup = BeautifulSoup(r.text, "xml")
                # İç sitemap'leri takip et
                for loc in soup.find_all("loc"):
                    u = loc.text.strip()
                    if u.endswith(".xml"):
                        try:
                            r2 = requests.get(u, timeout=15, headers={"User-Agent": USER_AGENT})
                            sub = BeautifulSoup(r2.text, "xml")
                            for sub_loc in sub.find_all("loc"):
                                urls.add(sub_loc.text.strip())
                        except Exception as e:
                            log.warning(f"Alt sitemap okunamadı: {u}: {e}")
                    else:
                        urls.add(u)
                if urls:
                    log.info(f"Sitemap'ten {len(urls)} URL bulundu: {sm_path}")
                    break
        except Exception as e:
            log.debug(f"{sm_path} alınamadı: {e}")

    # 2. RSS dene (sitemap başarısızsa veya tamamlamak için)
    try:
        feed = feedparser.parse(base_url + "/feed/")
        for entry in feed.entries:
            if entry.get("link"):
                urls.add(entry.link)
        log.info(f"RSS'ten {len(feed.entries)} URL eklendi.")
    except Exception as e:
        log.warning(f"RSS okunamadı: {e}")

    # WordPress yazı URL deseni (yıl/ay/gün/slug)
    post_urls = []
    for u in urls:
        path = urlparse(u).path
        # Tipik WP post: /YYYY/MM/DD/slug/  veya /YYYY/MM/DD/slug
        if re.match(r"^/\d{4}/\d{2}/\d{2}/.+", path):
            post_urls.append(u)

    log.info(f"Toplam {len(post_urls)} yazı URL'si bulundu.")
    return sorted(post_urls)


def html_to_markdown(html: str) -> str:
    """Basit HTML -> Markdown dönüşümü."""
    soup = BeautifulSoup(html, "html.parser")

    # Script ve style'ı sil
    for tag in soup(["script", "style"]):
        tag.decompose()

    # WordPress'in eklediği tipik yapı: makaleyi bul
    article = (
        soup.find("article")
        or soup.find("div", class_=re.compile(r"entry-content|post-content|article-content"))
        or soup.find("main")
        or soup
    )

    md_parts = []

    def process(node, depth=0):
        if not hasattr(node, "name") or node.name is None:
            text = str(node).strip()
            if text:
                md_parts.append(text)
            return

        name = node.name.lower()

        if name in ("script", "style", "nav", "footer", "header", "aside"):
            return
        if name == "br":
            md_parts.append("\n")
            return
        if name == "hr":
            md_parts.append("\n\n---\n\n")
            return
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            md_parts.append("\n\n" + ("#" * level) + " " + node.get_text(strip=True) + "\n\n")
            return
        if name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                md_parts.append("\n\n" + text + "\n\n")
            return
        if name == "strong" or name == "b":
            md_parts.append("**" + node.get_text(strip=True) + "**")
            return
        if name == "em" or name == "i":
            md_parts.append("*" + node.get_text(strip=True) + "*")
            return
        if name == "a":
            href = node.get("href", "")
            text = node.get_text(strip=True)
            if href and text:
                md_parts.append(f"[{text}]({href})")
            else:
                md_parts.append(text)
            return
        if name == "img":
            src = node.get("src", "")
            alt = node.get("alt", "")
            if src:
                md_parts.append(f"\n\n![{alt}]({src})\n\n")
            return
        if name == "ul":
            md_parts.append("\n")
            for li in node.find_all("li", recursive=False):
                md_parts.append("- " + li.get_text(" ", strip=True) + "\n")
            md_parts.append("\n")
            return
        if name == "ol":
            md_parts.append("\n")
            for i, li in enumerate(node.find_all("li", recursive=False), 1):
                md_parts.append(f"{i}. " + li.get_text(" ", strip=True) + "\n")
            md_parts.append("\n")
            return
        if name == "blockquote":
            text = node.get_text(" ", strip=True)
            md_parts.append("\n\n> " + text + "\n\n")
            return

        # Default: çocukları gez
        for child in node.children:
            process(child, depth + 1)

    process(article)
    md = "".join(md_parts)

    # Tekrarlayan boşlukları temizle
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r" {2,}", " ", md)
    return md.strip()


def parse_post_page(url: str) -> dict:
    """Bir yazı sayfasını çekip bilgileri çıkarır."""
    r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Başlık
    title_tag = soup.find("h1", class_=re.compile(r"entry-title|post-title")) or soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # OG meta yedek
    og_title = soup.find("meta", property="og:title")
    if not title and og_title:
        title = og_title.get("content", "")

    # Açıklama
    og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    excerpt = og_desc.get("content", "") if og_desc else ""

    # Kapak görseli
    og_img = soup.find("meta", property="og:image")
    featured = og_img.get("content", "") if og_img else ""

    # Yayın tarihi
    pub_time = soup.find("meta", property="article:published_time")
    published_at = None
    if pub_time:
        try:
            published_at = datetime.fromisoformat(pub_time.get("content", "").replace("Z", "+00:00"))
        except Exception:
            pass

    # URL'den slug çıkar
    path = urlparse(url).path.strip("/").split("/")
    slug = path[-1] if path else slugify(title)

    # Kategori (varsa breadcrumb veya tag'lerden)
    category_name = None
    cat_links = soup.find_all("a", rel="category tag") or soup.select(".cat-links a, .category a")
    if cat_links:
        category_name = cat_links[0].get_text(strip=True)

    # İçerik
    content_md = html_to_markdown(r.text)

    return {
        "url": url,
        "slug": slug,
        "title": title,
        "excerpt": excerpt,
        "content": content_md,
        "featured_image": featured,
        "published_at": published_at,
        "category_name": category_name,
    }


def get_or_create_category(name_tr: str) -> Category:
    if not name_tr:
        return None
    slug = slugify(name_tr)
    cat = db.session.query(Category).filter_by(slug=slug).first()
    if not cat:
        cat = Category(slug=slug, name_tr=name_tr)
        db.session.add(cat)
        db.session.flush()
    return cat


def import_post(post_data: dict, dry_run: bool = False):
    if not post_data["title"] or not post_data["content"]:
        log.warning(f"Atlandı (boş): {post_data['url']}")
        return None

    # Slug çakışıyorsa, geç
    existing = db.session.query(Post).filter_by(slug=post_data["slug"]).first()
    if existing:
        log.info(f"Zaten var (atlandı): {post_data['slug']}")
        return existing

    if dry_run:
        log.info(f"[DRY] {post_data['title']} ({post_data['slug']}) - {len(post_data['content'])} kar.")
        return None

    cat = get_or_create_category(post_data.get("category_name"))

    post = Post(
        slug=post_data["slug"],
        status="published",
        category_id=cat.id if cat else None,
        featured_image=post_data.get("featured_image") or None,
        published_at=post_data.get("published_at") or datetime.utcnow(),
        original_url=post_data["url"],
    )
    db.session.add(post)
    db.session.flush()

    translation = PostTranslation(
        post_id=post.id,
        language="tr",
        title=post_data["title"][:500],
        excerpt=post_data["excerpt"][:500] if post_data["excerpt"] else None,
        content=post_data["content"],
        is_published=True,
    )
    db.session.add(translation)
    db.session.commit()
    log.info(f"✓ Aktarıldı: {post_data['title']}")
    return post


def main():
    parser = argparse.ArgumentParser(description="WordPress -> Yeni blog migrasyonu")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--limit", type=int, default=0, help="0 = limitsiz")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        urls = fetch_post_urls(args.source)
        if args.limit:
            urls = urls[: args.limit]

        log.info(f"İçe aktarılacak URL sayısı: {len(urls)}")

        success, fail = 0, 0
        for i, url in enumerate(urls, 1):
            try:
                log.info(f"[{i}/{len(urls)}] İndiriliyor: {url}")
                data = parse_post_page(url)
                if import_post(data, dry_run=args.dry_run):
                    success += 1
            except Exception as e:
                log.error(f"Hata: {url}: {e}")
                fail += 1

        log.info(f"BİTTİ: {success} başarılı, {fail} hata.")


if __name__ == "__main__":
    main()
