import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = (
    os.environ.get("TELEGRAM_TARGET_CHAT_ID")
    or os.environ.get("TELEGRAM_GROUP_ID")
)

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN else None
)

def telegram_call(method, payload=None):
    if not TELEGRAM_API:
        raise RuntimeError("Telegram bot token is not configured")

    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        json=payload or {},
        timeout=30
    )
    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError("Telegram API request failed")

    return result["result"]


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "service": "Mogok Karaoke Bot"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/submit-link", methods=["POST"])
def submit_link():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url.startswith((
        "https://www.youtube.com/",
        "https://youtube.com/",
        "https://youtu.be/"
    )):
        return jsonify({
            "ok": False,
            "error": "Invalid HTTPS YouTube URL"
        }), 400

    if not BOT_TOKEN or not CHAT_ID:
        return jsonify({
            "ok": False,
            "error": "Telegram settings missing"
        }), 500

    try:
        telegram_call("sendMessage", {
            "chat_id": CHAT_ID,
            "text": f"🎵 Link from Mogok Karaoke App:\n{url}"
        })
        return jsonify({"ok": True})
    except Exception:
        app.logger.exception("Telegram send failed")
        return jsonify({
            "ok": False,
            "error": "Telegram send failed"
        }), 502


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("channel_post")

    if not message:
        return jsonify({"ok": True})

    chat = message.get("chat", {})
    if CHAT_ID and str(chat.get("id")) != str(CHAT_ID):
        return jsonify({"ok": True})

    video = message.get("video") or message.get("document")

    if video:
        return jsonify({
            "ok": True,
            "video": {
                "file_id": video.get("file_id"),
                "file_name": (
                    video.get("file_name")
                    or "telegram_video"
                ),
                "mime_type": video.get("mime_type"),
                "file_size": video.get("file_size")
            }
        })

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
