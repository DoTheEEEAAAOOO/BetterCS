import art
from flask import Flask

print(art.text2art("B e t t e r C S", font="big", chr_ignore=True))
print("Initting")

app = Flask(__name__)

@app.route("/")
def home():
    return ""

if __name__ == "__main__":
    app.run(debug=True)