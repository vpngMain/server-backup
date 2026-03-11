"""Globální obsluha chyb – vlastní stránky 404 a 500."""
from flask import Flask, render_template, redirect, url_for, request
from flask_wtf.csrf import CSRFError


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def handle_csrf_error(_e):
        # U loginu vrátíme uživatele zpět na přihlášení, jinde zobrazíme 400 text.
        if request.path == "/login":
            return redirect(url_for("auth.login", error="invalid"))
        return "Neplatný CSRF token. Obnovte stránku a zkuste to znovu.", 400

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
