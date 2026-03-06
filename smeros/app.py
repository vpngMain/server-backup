from flask import Flask, render_template

app = Flask(__name__)

apps = [
    {
        "name": "Odběros",
        "port": 8081,
        "description": "Systém pro odběry a PPL",
        "icon": "📦"
    },
    {
        "name": "Objednávač",
        "port": 8082,
        "description": "Interní objednávkový systém",
        "icon": "🧾"
    }
]


@app.route("/")
def index():
    return render_template("index.html", apps=apps)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
