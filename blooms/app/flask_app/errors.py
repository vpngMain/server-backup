"""Globální obsluha chyb – vlastní stránky 404 a 500."""
from flask import Flask, render_template


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500
