from flask import Flask
from .routes.email import email_bp
from .routes.config import config_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(email_bp)
    app.register_blueprint(config_bp)
    try:
        from .services.classifier_service import classifier_service
    except Exception as _:
        pass
    return app

