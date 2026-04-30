"""
Internal API: AI özellikleri için JSON endpoint'leri.
Hepsi admin login gerektirir.
"""
import os

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from extensions import db, limiter
from models import Post, PostTranslation, TopicSuggestion, AILog
from services.ai_writer import AIWriter
from services.topic_finder import TopicFinder
from services.translator import Translator
from services.seo import SEOGenerator
from services.enhancer import Enhancer

api_bp = Blueprint("api", __name__)


# --- Konu önerileri --------------------------------------------------------

@api_bp.route("/topics/discover", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def discover_topics():
    """
    Web search + AI ile güncel ortopedi konu önerileri üretir.
    Sonuçları TopicSuggestion tablosuna yazar.
    """
    data = request.get_json(silent=True) or {}
    focus = data.get("focus", "ortopedi, travmatoloji, boy uzatma, deformite, kırık")
    count = min(int(data.get("count", 5)), 10)

    finder = TopicFinder(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        suggestions = finder.discover(focus=focus, count=count)
    except Exception as e:
        current_app.logger.exception("Topic discovery error")
        _log_ai("topics", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    saved = []
    for s in suggestions:
        ts = TopicSuggestion(
            title=s["title"],
            description=s.get("description", ""),
            relevance_score=s.get("relevance_score", 0.5),
            sources=str(s.get("sources", [])),
            keywords=", ".join(s.get("keywords", [])),
        )
        db.session.add(ts)
        saved.append(ts)
    db.session.commit()
    _log_ai("topics", success=True)

    return jsonify({
        "topics": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "keywords": t.keywords,
                "relevance_score": t.relevance_score,
            }
            for t in saved
        ]
    })


# --- Yazı yazma ------------------------------------------------------------

@api_bp.route("/posts/generate", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def generate_post():
    """
    AI ile, hocanın tarzında, verilen konuda blog yazısı oluşturur.
    Otomatik kaydetmez; düzenleyiciye taslak içerik döner.
    """
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    topic_id = data.get("topic_id")
    target_words = int(data.get("target_words", 800))
    tone_examples = data.get("tone_examples")  # Opsiyonel: özel örnek metinler

    if not topic and topic_id:
        ts = db.session.get(TopicSuggestion, int(topic_id))
        if ts:
            topic = ts.title

    if not topic:
        return jsonify({"error": "Konu belirtilmedi"}), 400

    # Tarz örneklerini son 3-5 yayınlanmış TR yazıdan al
    if not tone_examples:
        examples = (
            db.session.query(PostTranslation)
            .filter_by(language="tr", is_published=True)
            .order_by(PostTranslation.created_at.desc())
            .limit(4)
            .all()
        )
        tone_examples = [
            {"title": e.title, "content": e.content[:3000]} for e in examples
        ]

    writer = AIWriter(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        result = writer.write_post(
            topic=topic,
            target_words=target_words,
            tone_examples=tone_examples,
            author_name=current_app.config["AUTHOR_NAME"],
        )
    except Exception as e:
        current_app.logger.exception("AI write error")
        _log_ai("write", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    # Konu önerisini kullanıldı olarak işaretle
    if topic_id:
        ts = db.session.get(TopicSuggestion, int(topic_id))
        if ts:
            ts.status = "used"
            db.session.commit()

    _log_ai(
        "write",
        success=True,
        in_tokens=result.get("input_tokens"),
        out_tokens=result.get("output_tokens"),
    )
    return jsonify(result)


# --- Mevcut yazıyı geliştirme ----------------------------------------------

@api_bp.route("/posts/<int:post_id>/enhance", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def enhance_post(post_id):
    """Mevcut bir yazıyı günceller, genişletir ve geliştirir."""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Yazı bulunamadı"}), 404

    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "tr")
    mode = data.get("mode", "improve")  # improve, expand, modernize, shorten

    translation = next((t for t in post.translations if t.language == lang), None)
    if not translation:
        return jsonify({"error": "Bu dilde çeviri yok"}), 404

    enhancer = Enhancer(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        result = enhancer.enhance(
            title=translation.title,
            content=translation.content,
            mode=mode,
        )
    except Exception as e:
        current_app.logger.exception("Enhance error")
        _log_ai("enhance", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    _log_ai(
        "enhance",
        success=True,
        in_tokens=result.get("input_tokens"),
        out_tokens=result.get("output_tokens"),
    )
    return jsonify(result)


# --- Çeviri ----------------------------------------------------------------

@api_bp.route("/posts/<int:post_id>/translate", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def translate_post(post_id):
    """
    Bir yazıyı hedef dile çevirir ve TASLAK olarak kaydeder.
    Yayın için admin'in onaylaması gerekir (ai_review_pending=True).
    """
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Yazı bulunamadı"}), 404

    data = request.get_json(silent=True) or {}
    target_lang = data.get("target_lang")
    if target_lang not in ("en", "ar"):
        return jsonify({"error": "Geçersiz dil. en veya ar olmalı."}), 400

    source = next((t for t in post.translations if t.language == "tr"), None)
    if not source:
        return jsonify({"error": "Türkçe kaynak yok"}), 400

    translator = Translator(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        result = translator.translate(
            title=source.title,
            content=source.content,
            excerpt=source.excerpt or "",
            meta_title=source.meta_title or "",
            meta_description=source.meta_description or "",
            target_lang=target_lang,
        )
    except Exception as e:
        current_app.logger.exception("Translate error")
        _log_ai("translate", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    # Hedef dilde mevcut çeviri varsa güncelle, yoksa oluştur
    target = next((t for t in post.translations if t.language == target_lang), None)
    if not target:
        target = PostTranslation(post_id=post.id, language=target_lang, title=result["title"], content=result["content"])
        db.session.add(target)
    target.title = result["title"]
    target.content = result["content"]
    target.excerpt = result.get("excerpt", "")
    target.meta_title = result.get("meta_title", "")
    target.meta_description = result.get("meta_description", "")
    target.is_ai_translated = True
    target.ai_review_pending = True   # ÖNEMLİ: Onay bekliyor
    target.is_published = False       # Onaylanana kadar yayında değil

    db.session.commit()
    _log_ai("translate", success=True, in_tokens=result.get("input_tokens"), out_tokens=result.get("output_tokens"))

    return jsonify({
        "ok": True,
        "translation_id": target.id,
        "review_url": f"/admin/posts/{post.id}/edit?lang={target_lang}",
        "preview": {
            "title": target.title,
            "excerpt": target.excerpt,
        }
    })


# --- SEO meta üretimi ------------------------------------------------------

@api_bp.route("/posts/<int:post_id>/seo", methods=["POST"])
@login_required
@limiter.limit("60 per hour")
def generate_seo(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Yazı bulunamadı"}), 404
    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "tr")
    translation = next((t for t in post.translations if t.language == lang), None)
    if not translation:
        return jsonify({"error": "Bu dilde çeviri yok"}), 404

    seo = SEOGenerator(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        result = seo.generate(title=translation.title, content=translation.content, lang=lang)
    except Exception as e:
        current_app.logger.exception("SEO error")
        _log_ai("seo", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    _log_ai("seo", success=True, in_tokens=result.get("input_tokens"), out_tokens=result.get("output_tokens"))
    return jsonify(result)


# --- Görsel önerisi --------------------------------------------------------

@api_bp.route("/posts/<int:post_id>/image-suggestions", methods=["POST"])
@login_required
@limiter.limit("60 per hour")
def image_suggestions(post_id):
    """Yazı için görsel arama anahtar kelimeleri ve alt-text önerir."""
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Yazı bulunamadı"}), 404
    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "tr")
    translation = next((t for t in post.translations if t.language == lang), None)
    if not translation:
        return jsonify({"error": "Bu dilde çeviri yok"}), 404

    writer = AIWriter(api_key=current_app.config["ANTHROPIC_API_KEY"], model=current_app.config["AI_MODEL"])
    try:
        result = writer.suggest_images(title=translation.title, content=translation.content)
    except Exception as e:
        current_app.logger.exception("Image suggestion error")
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


# --- AI Kapak Görseli Üretimi ---------------------------------------------

@api_bp.route("/posts/<int:post_id>/generate-cover", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def generate_cover(post_id):
    """
    OpenAI ile yazı için kapak görseli üretir.
    Gereksinimler:
      - ANTHROPIC_API_KEY (prompt için)
      - OPENAI_API_KEY (görsel üretimi için)
    Üretilen görseli /static/images/uploads/ altına kaydeder, URL döner.
    """
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({"error": "Yazı bulunamadı"}), 404

    openai_key = (current_app.config.get("OPENAI_API_KEY")
                  or os.environ.get("OPENAI_API_KEY"))
    if not openai_key:
        return jsonify({
            "error": "OPENAI_API_KEY env var tanımlı değil. "
                     "Railway → Variables'a OPENAI_API_KEY=sk-... ekleyin."
        }), 503

    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "tr")
    quality = data.get("quality", os.environ.get("IMAGE_QUALITY", "medium"))
    save_as_cover = data.get("save_as_cover", True)

    translation = next((t for t in post.translations if t.language == lang), None)
    if not translation:
        return jsonify({"error": "Bu dilde çeviri yok"}), 404

    try:
        from services.image_generator import ImageGenerator
    except ImportError as e:
        return jsonify({"error": f"image_generator yüklenemedi: {e}"}), 500

    try:
        gen = ImageGenerator(
            anthropic_key=current_app.config["ANTHROPIC_API_KEY"],
            openai_key=openai_key,
            claude_model=current_app.config["AI_MODEL"],
            image_model=os.environ.get("IMAGE_MODEL", "gpt-image-1"),
            image_quality=quality,
        )
        result = gen.generate(
            title=translation.title,
            excerpt=translation.excerpt or "",
            upload_dir=current_app.config["UPLOAD_FOLDER"],
        )
    except RuntimeError as e:
        # Beklenen hata mesajları (kredi/moderation vb.)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.exception("Cover generation error")
        _log_ai("generate_cover", success=False, error=str(e))
        return jsonify({"error": str(e)}), 500

    # Yazıya kapak olarak otomatik ata
    if save_as_cover:
        post.featured_image = result["url"]
        db.session.commit()

    _log_ai("generate_cover", success=True)
    return jsonify({
        "ok": True,
        "url": result["url"],
        "filename": result["filename"],
        "prompt": result["prompt"],
        "size_bytes": result["size_bytes"],
        "model": result["model"],
        "saved_as_cover": save_as_cover,
    })


# --- Yardımcı --------------------------------------------------------------

def _log_ai(operation, success=True, error=None, in_tokens=None, out_tokens=None):
    try:
        log = AILog(
            operation=operation,
            user_id=current_user.id if current_user.is_authenticated else None,
            success=success,
            error=error,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
