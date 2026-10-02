import art
from flask import Flask, send_from_directory
from pathlib import Path

print(art.text2art("B e t t e r C S", font="big", chr_ignore=True))
print("Initting")

base_dir = Path(__file__).resolve().parent
workspace_dir = base_dir.parents[1]
pages_dir = base_dir / "pages"
backend_dir = base_dir / "backend"
components_dir = base_dir / "components"
style_dir = base_dir / "style"
lib_dir = base_dir / "lib"
assets_dir = workspace_dir / "src" / "assets"
audio_dir = workspace_dir / "progs" / "assets"

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

@app.route("/backend/<path:filename>")
def backend_asset(filename):
    return send_from_directory(backend_dir, filename)

@app.route("/components/<path:filename>")
def component_asset(filename):
    return send_from_directory(components_dir, filename)

@app.route("/style/<path:filename>")
def style_asset(filename):
    return send_from_directory(style_dir, filename)

@app.route("/lib/<path:filename>")
def library_asset(filename):
    return send_from_directory(lib_dir, filename)

@app.route("/assets/<path:filename>")
def asset(filename):
    return send_from_directory(assets_dir, filename)

@app.route("/audio/<path:filename>")
def audio_asset(filename):
    return send_from_directory(audio_dir, filename)

if __name__ == "__main__":
    app.run(debug=True)