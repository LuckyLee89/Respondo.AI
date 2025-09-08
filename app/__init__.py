from flask import Flask
from .routes.email import email_bp
from .routes.config import config_bp
from .routes.health import health_bp
from .routes.auth import auth_bp
from datetime import timedelta
import os
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("APP_SECRET", "dev-secret-change-me")
    app.config.update(
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),   # "lembrar" por 7 dias
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "1") == "1",  # em HTTPS/Render fica True
    )
    app.register_blueprint(auth_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

    try:
        from .services.classifier_service import classifier_service
    except Exception as _:
        pass
    return app

