from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "<h1>I've seen the future and it's getting better all the time.</h1>"


if __name__ == "__main__":
    app.run(debug=True)
