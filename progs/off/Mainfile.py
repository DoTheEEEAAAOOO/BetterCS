import art
from flask import Flask, send_from_directory
from pathlib import Path

print(art.text2art("B e t t e r C S", font="big", chr_ignore=True))
print("Initting")

base_dir = Path(__file__).resolve().parent
workspace_dir = base_dir.parents[1]
pages_dir = base_dir / "pages"
style_dir = base_dir / "style"
assets_dir = workspace_dir / "src" / "assets"
node_modules_dir = workspace_dir / "src" / "node_modules"

pages = {}
for page in pages_dir.glob("*.html"):
    pages[page.name] = page.read_text(encoding="utf-8")

app = Flask(__name__)

@app.route("/")
def home():
    return pages["Load.html"]

@app.route("/pages/<path:filename>")
def page_asset(filename):
    return send_from_directory(pages_dir, filename)

@app.route("/style/<path:filename>")
def style_asset(filename):
    return send_from_directory(style_dir, filename)

@app.route("/assets/<path:filename>")
def asset(filename):
    return send_from_directory(assets_dir, filename)

@app.route("/node_modules/<path:filename>")
def node_module(filename):
    return send_from_directory(node_modules_dir, filename)

if __name__ == "__main__":
    app.run(debug=True)