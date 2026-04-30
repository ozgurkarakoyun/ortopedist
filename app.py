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
