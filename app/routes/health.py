from flask import Blueprint, jsonify
import os

health_bp = Blueprint("health", __name__)

@health_bp.get("/healthz")
def healthz():
    return jsonify({
        "ok": True,
        "provider": os.getenv("PROVIDER", "").lower(),
        "require_ai": os.getenv("REQUIRE_AI", "true").lower(),
        "model_openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "force_api_classify": os.getenv("FORCE_API_CLASSIFY","0"),
    })
