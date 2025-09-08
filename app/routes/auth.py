from flask import Blueprint, render_template, request, redirect, session, url_for
import os

auth_bp = Blueprint("auth", __name__)

PUBLIC_PATHS = {
    "/login",
    "/health",
    "/static/",
    "/config",
}

@auth_bp.before_app_request
def _require_login():
    from flask import request
    p = request.path or "/"
    if any(p == r or p.startswith(r) for r in PUBLIC_PATHS):
        return
    if not session.get("auth"):
        return redirect(url_for("auth.login"))

@auth_bp.get("/login")
def login():
    if session.get("auth"):
        return redirect(url_for("email.index"))
    return render_template("login.html")

@auth_bp.post("/login")
def do_login():
    form_pass = (request.form.get("password") or "").strip()
    real_pass = os.getenv("LOGIN_PASSWORD", "admin")
    if form_pass and form_pass == real_pass:
        session["auth"] = True
        session.permanent = True
        return redirect(url_for("email.index"))
    return render_template("login.html", error="Senha inválida.")

@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
