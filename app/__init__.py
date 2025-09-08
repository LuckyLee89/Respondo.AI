from flask import Flask
from .routes.email import email_bp
from .routes.config import config_bp
from .routes.health import health_bp
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.register_blueprint(email_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

    try:
        from .services.classifier_service import classifier_service
    except Exception as _:
        pass
    return app

