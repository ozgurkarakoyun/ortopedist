"""
WXR (WordPress eXtended RSS) importer.
WordPress'in resmi export XML formatını parse eder ve
veritabanına Post + PostTranslation olarak ekler.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from typing import List, Dict, Optional, Iterator

from slugify import slugify
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def html_to_markdown(html: str) -> str:
    """WordPress HTML içeriğini sade Markdown'a çevirir."""
    if not html:
        return ""
    # Gutenberg blok yorumlarını temizle
    html = re.sub(r"<!--\s*/?wp:[^>]*-->", "", html)

    soup = BeautifulSoup(html, "html.parser")
    parts: List[str] = []

    def walk(node):
        if isinstance(node, str):
            text = node
            if text.strip():
                parts.append(text)
            return
        if not hasattr(node, "name") or node.name is None:
            return

        n = node.name.lower()

        if n in ("script", "style"):
            return
        if n == "br":
            parts.append("\n")
            return
        if n == "hr":
            parts.append("\n\n---\n\n")
            return
        if n in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(n[1])
            text = node.get_text(" ", strip=True)
            if text:
                parts.append("\n\n" + ("#" * level) + " " + text + "\n\n")
            return
        if n == "p":
            # paragraf içindeki çocukları işle (bağlantı/strong gibi inline öğeler için)
            inner = []
            for child in node.children:
                inner_part = _inline(child)
                if inner_part:
                    inner.append(inner_part)
            text = "".join(inner).strip()
            if text:
                parts.append("\n\n" + text + "\n\n")
            return
        if n == "blockquote":
            text = node.get_text(" ", strip=True)
            parts.append("\n\n> " + text + "\n\n")
            return
        if n == "ul":
            parts.append("\n")
            for li in node.find_all("li", recursive=False):
                parts.append("- " + li.get_text(" ", strip=True) + "\n")
            parts.append("\n")
            return
        if n == "ol":
            parts.append("\n")
            for i, li in enumerate(node.find_all("li", recursive=False), 1):
                parts.append(f"{i}. " + li.get_text(" ", strip=True) + "\n")
            parts.append("\n")
            return
        if n == "img":
            src = node.get("src", "")
            alt = node.get("alt", "")
            if src:
                parts.append(f"\n\n![{alt}]({src})\n\n")
            return
        if n == "figure":
            # WordPress figure: img + figcaption
            img = node.find("img")
            cap = node.find("figcaption")
            if img:
                src = img.get("src", "")
                alt = img.get("alt", "") or (cap.get_text(strip=True) if cap else "")
                if src:
                    parts.append(f"\n\n![{alt}]({src})")
                    if cap:
                        parts.append(f"\n*{cap.get_text(strip=True)}*")
                    parts.append("\n\n")
            return
        if n == "iframe":
            # YouTube vb. embed -> bağlantı olarak kaydet
            src = node.get("src", "")
            if src:
                parts.append(f"\n\n[Video]({src})\n\n")
            return

        # Diğer container'lar (div, section, article) için çocuklara in
        for child in node.children:
            walk(child)

    def _inline(node) -> str:
        """Inline element'leri (a, strong, em, code, span) markdown'a çevirir."""
        if isinstance(node, str):
            return node
        if not hasattr(node, "name") or node.name is None:
            return ""
        n = node.name.lower()
        if n == "a":
            href = node.get("href", "")
            text = node.get_text(strip=True)
            if href and text:
                return f"[{text}]({href})"
            return text
        if n in ("strong", "b"):
            return "**" + node.get_text(strip=True) + "**"
        if n in ("em", "i"):
            return "*" + node.get_text(strip=True) + "*"
        if n == "code":
            return "`" + node.get_text(strip=True) + "`"
        if n == "br":
            return "\n"
        if n == "img":
            src = node.get("src", "")
            alt = node.get("alt", "")
            if src:
                return f"![{alt}]({src})"
            return ""
        # Diğer inline'lar için iç text
        return "".join(_inline(c) for c in node.children)

    walk(soup)
    md = "".join(parts)

    # Temizlik
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = re.sub(r"[ \t]{2,}", " ", md)
    return md.strip()


def parse_wxr(xml_path: str) -> Iterator[Dict]:
    """WXR dosyasını parse edip her yazıyı dict olarak yield eder."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        return

    for item in channel.findall("item"):
        post_type = item.findtext("wp:post_type", namespaces=NS) or ""
        status = item.findtext("wp:status", namespaces=NS) or ""
        if post_type != "post" or status != "publish":
            continue

        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        slug_wp = (item.findtext("wp:post_name", namespaces=NS) or "").strip()
        date_str = (item.findtext("wp:post_date_gmt", namespaces=NS) or
                    item.findtext("wp:post_date", namespaces=NS) or "")

        # İçerik — content:encoded
        content_node = item.find("content:encoded", namespaces=NS)
        content_html = content_node.text if content_node is not None and content_node.text else ""

        # Özet
        excerpt_node = item.find("excerpt:encoded", namespaces=NS)
        excerpt = (excerpt_node.text if excerpt_node is not None and excerpt_node.text else "").strip()

        # Kategoriler ve etiketler
        categories = []
        tags = []
        for cat in item.findall("category"):
            domain = cat.get("domain", "")
            name = (cat.text or "").strip()
            if not name:
                continue
            if domain == "category":
                categories.append(name)
            elif domain == "post_tag":
                tags.append(name)

        # Kapak görseli — _thumbnail_id varsa attachment'a referans verir
        # Daha basitçe içerikten ilk img'i al
        featured_image = None
        if content_html:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content_html)
            if m:
                featured_image = m.group(1)
            # OG image meta'sı varsa onu öncelikle al
            for meta in item.findall("wp:postmeta", namespaces=NS):
                key = meta.findtext("wp:meta_key", namespaces=NS) or ""
                value = meta.findtext("wp:meta_value", namespaces=NS) or ""
                if key in ("_jetpack_post_thumbnail", "og_image", "_yoast_wpseo_opengraph-image"):
                    if value.startswith("http"):
                        featured_image = value
                        break

        # Tarih parse
        published_at = None
        if date_str and not date_str.startswith("0000"):
            try:
                published_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        # Slug fallback
        slug = slug_wp or slugify(title)

        # Markdown'a çevir
        content_md = html_to_markdown(unescape(content_html or ""))

        yield {
            "title": title,
            "slug": slug,
            "link": link,
            "excerpt": excerpt,
            "content": content_md,
            "content_html": content_html,
            "featured_image": featured_image,
            "categories": categories,
            "tags": tags,
            "published_at": published_at,
        }
