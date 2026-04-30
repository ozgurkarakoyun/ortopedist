"""
Ortopedist Blog - Ana Flask uygulaması.
"""
import os
import logging
from flask import Flask, request, session, g, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

from config import Config
from extensions import db, migrate, login_manager, babel, csrf, limiter
from models import User


def select_locale():
    """Kullanıcının dil tercihini belirle (URL > session > tarayıcı)."""
    # 1. URL prefix'inden (/en/..., /ar/...)
    if request.view_args and "lang" in request.view_args:
        lang = request.view_args["lang"]
        if lang in Config.LANGUAGES:
            session["lang"] = lang
            return lang
    # 2. Session
    if "lang" in session and session["lang"] in Config.LANGUAGES:
        return session["lang"]
    # 3. Tarayıcı
    return request.accept_languages.best_match(list(Config.LANGUAGES.keys())) or "tr"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _sync_admin_from_env(app):
    """
    ADMIN_EMAIL ve ADMIN_PASSWORD env var'ları varsa:
    - O e-posta ile kullanıcı yoksa: oluşturur
    - Varsa: şifresini env'deki değere set eder (şifre unutma kolaylığı)
    Sessiz çalışır (hata loglar, raise etmez).
    """
    admin_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD") or ""
    admin_name = os.environ.get("ADMIN_NAME") or "Admin"

    if not admin_email or not admin_password:
        return  # env var'lar yoksa hiç dokunma

    # Şifrede ASCII olmayan karakter varsa uyar (cookie imza hatası önle)
    try:
        admin_password.encode("ascii")
    except UnicodeEncodeError:
        app.logger.warning(
            "ADMIN_PASSWORD ASCII olmayan karakter içeriyor (ş, ğ, ü vb.). "
            "Cookie imza hatası riskine karşı sadece ASCII karakter kullanın."
        )

    with app.app_context():
        try:
            existing = db.session.query(User).filter_by(email=admin_email).first()
            if existing:
                existing.set_password(admin_password)
                existing.is_active_user = True
                existing.role = "admin"
                if admin_name and existing.name != admin_name:
                    existing.name = admin_name
                db.session.commit()
                app.logger.info(f"Admin şifresi env'den güncellendi: {admin_email}")
            else:
                u = User(
                    email=admin_email,
                    name=admin_name,
                    role="admin",
                    is_active_user=True,
                )
                u.set_password(admin_password)
                db.session.add(u)
                db.session.commit()
                app.logger.info(f"Admin env'den oluşturuldu: {admin_email}")
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            app.logger.warning(f"Admin senkronizasyonu başarısız: {e}")


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    # Loglama
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Yükleme klasörü
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Uzantıları başlat
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    babel.init_app(app, locale_selector=select_locale)

    # Blueprint'leri kaydet
    from routes.public import public_bp
    from routes.admin import admin_bp
    from routes.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # CSRF muafiyetini sadece API için (gerekirse)
    csrf.exempt(api_bp)

    # Şablonlara global değişkenler
    @app.context_processor
    def inject_globals():
        from flask_babel import get_locale
        current_lang = str(get_locale() or "tr")
        return {
            "site_name": app.config["SITE_NAME"],
            "site_url": app.config["SITE_URL"],
            "author_name": app.config["AUTHOR_NAME"],
            "languages": app.config["LANGUAGES"],
            "current_lang": current_lang,
            "is_rtl": current_lang == "ar",
        }

    # Şablonlardan kullanılacak: lang_url('en') -> mevcut sayfanın EN versiyonu
    @app.context_processor
    def inject_lang_url():
        def lang_url(target_lang):
            ep = request.endpoint or "public.index"
            args = request.view_args or {}

            def home(lang):
                if lang == "tr":
                    return url_for("public.index")
                return url_for(f"public.index_{lang}")

            # Tek yazı sayfaları
            if ep in ("public.post_tr", "public.post_en", "public.post_ar"):
                slug = args.get("slug")
                if slug:
                    if target_lang == "tr":
                        return url_for("public.post_tr", slug=slug)
                    return url_for(f"public.post_{target_lang}", slug=slug)
                return home(target_lang)

            # Kategori sayfaları
            if ep == "public.category":
                slug = args.get("slug")
                if slug:
                    if target_lang == "tr":
                        return url_for("public.category", slug=slug)
                    return url_for("public.category", slug=slug, lang=target_lang)
                return home(target_lang)

            # about / contact / search (lang param destekli endpoint'ler)
            if ep in ("public.about", "public.contact", "public.search"):
                if target_lang == "tr":
                    return url_for(ep)
                return url_for(ep, lang=target_lang)

            # Ana sayfa varyantları
            if ep in ("public.index", "public.index_en", "public.index_ar"):
                return home(target_lang)

            # Diğer her şey için ana sayfaya
            return home(target_lang)

        return {"lang_url": lang_url}

    # Dil değiştirme endpoint'i
    @app.route("/set-language/<lang>")
    def set_language(lang):
        if lang in app.config["LANGUAGES"]:
            session["lang"] = lang
        return redirect(request.referrer or url_for("public.index"))

    # Hata sayfaları
    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("public/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        app.logger.exception("Sunucu hatası")
        return render_template("public/500.html"), 500

    # Sağlık kontrolü (DB'ye dokunmaz, Railway healthcheck için)
    @app.route("/healthz")
    def healthz():
        return {"ok": True}, 200

    # İlk deploy'da tabloları otomatik oluştur (idempotent)
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("DB tabloları kontrol edildi/oluşturuldu.")
        except Exception as e:
            app.logger.warning(f"db.create_all() başarısız (DB henüz hazır olmayabilir): {e}")

    # ADMIN_EMAIL + ADMIN_PASSWORD env var'ları varsa, admin'i her boot'ta senkronize et
    # - Yoksa oluşturur
    # - Varsa şifresini env'deki değere güncel tutar (şifre unutma rahatlığı)
    _sync_admin_from_env(app)

    # CLI komutları
    @app.cli.command("init-db")
    def init_db_cmd():
        """Veritabanı tablolarını oluşturur."""
        db.create_all()
        print("Veritabanı tabloları oluşturuldu.")

    @app.cli.command("create-admin")
    def create_admin_cmd():
        """İnteraktif admin kullanıcısı oluşturur."""
        import getpass
        email = input("Admin e-posta: ").strip()
        name = input("İsim: ").strip()
        pw = getpass.getpass("Şifre: ")
        if not email or not pw:
            print("E-posta ve şifre zorunlu.")
            return
        u = User(email=email, name=name or "Admin", role="admin")
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        print(f"Admin oluşturuldu: {email}")

    return app


# Railway / Gunicorn için modül seviyesinde uygulama
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
