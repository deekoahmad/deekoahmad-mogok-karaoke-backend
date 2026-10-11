import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = (
    os.environ.get("TELEGRAM_TARGET_CHAT_ID")
    or os.environ.get("TELEGRAM_GROUP_ID")
)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "service": "Mogok Karaoke Bot"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/submit-link", methods=["POST"])
def submit_link():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url.startswith(("https://www.youtube.com/",
                           "https://youtube.com/",
                           "https://youtu.be/")):
        return jsonify({
            "ok": False,
            "error": "Please provide a valid HTTPS YouTube link"
        }), 400

    if not BOT_TOKEN or not CHAT_ID:
        return jsonify({
            "ok": False,
            "error": "Telegram environment variables are missing"
        }), 500

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(
            api_url,
            json={
                "chat_id": CHAT_ID,
                "text": f"🎵 New link from Mogok Karaoke App:\n{url}"
            },
            timeout=20
        )

        result = response.json()

        if response.ok and result.get("ok"):
            return jsonify({
                "ok": True,
                "message": "Link sent to Telegram"
            })

        print("Telegram API error:", result)
        return jsonify({
            "ok": False,
            "error": "Telegram rejected the message"
        }), 502

    except requests.RequestException as exc:
        print("Telegram connection error:", str(exc))
        return jsonify({
            "ok": False,
            "error": "Could not connect to Telegram"
        }), 502


@app.route("/telegram-test", methods=["POST"])
def telegram_test():
    key = os.environ.get("TELEGRAM_TEST_KEY")
    supplied_key = request.headers.get("X-Test-Key")

    if not key or supplied_key != key:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    if not BOT_TOKEN or not CHAT_ID:
        return jsonify({
            "ok": False,
            "error": "Telegram settings missing"
        }), 500

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": "✅ Mogok Karaoke Telegram connection test"
            },
            timeout=20
        )
        result = response.json()

        if response.ok and result.get("ok"):
            return jsonify({"ok": True, "message": "Telegram message sent"})

        print("Telegram API error:", result)
        return jsonify({
            "ok": False,
            "error": result.get("description", "Telegram API error")
        }), 502

    except requests.RequestException as exc:
        print("Telegram connection error:", str(exc))
        return jsonify({"ok": False, "error": "Connection failed"}), 502
        
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
