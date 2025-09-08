import os
from flask import Blueprint, jsonify, url_for

config_bp = Blueprint("config", __name__)

@config_bp.get("/config")
def get_config():
    company_name = os.getenv("COMPANY_NAME", "AutoU").strip() or "AutoU"

    # por padrão, procura por /static/logo.png
    default_logo = url_for("static", filename="logo.png")
    logo_url = os.getenv("LOGO_URL", default_logo).strip() or default_logo

    primary_color = os.getenv("PRIMARY_COLOR", "").strip()

    return jsonify({
        "ok": True,
        "company_name": company_name,
        "logo_url": logo_url,
        "primary_color": primary_color
    })
