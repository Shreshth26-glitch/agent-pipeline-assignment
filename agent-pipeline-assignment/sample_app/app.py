"""Minimal Flask app standing in for the 'small provided repo' the CI/CD
pipeline in Part 3 runs against."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify(status="ok"), 200


@app.route("/version")
def version():
    return jsonify(version="1.0.0"), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
