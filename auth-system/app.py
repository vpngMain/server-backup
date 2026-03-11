"""Centrální auth systém: API + admin web."""
import os
from flask import Flask, redirect, url_for
from models import db, User
from api.routes import api_bp
from admin.routes import admin_bp

app = Flask(__name__)


@app.route("/")
def index():
    return redirect(url_for("admin.login"))
app.config.from_object("config")
db.init_app(app)

app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)

os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)


with app.app_context():
    db.create_all()
    # První admin, pokud v DB není žádný uživatel (jméno: admin, PIN: 1234 – po přihlášení změňte)
    if User.query.count() == 0:
        admin = User(username="admin", role="admin", active=True)
        admin.set_pin("1234")
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
