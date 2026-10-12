
import os
import re
import sqlite3
import requests

from flask import Flask, request, jsonify, Response
from werkzeug.utils import secure_filename
from threading import Lock

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = (
    os.environ.get("TELEGRAM_TARGET_CHAT_ID", "").strip()
    or os.environ.get("TELEGRAM_GROUP_ID", "").strip()
)
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
TEST_KEY = os.environ.get("TELEGRAM_TEST_KEY", "").strip()

DB_PATH = os.environ.get("DB_PATH", "/tmp/mogok_videos.db")
db_lock = Lock()


def telegram_api(method):
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                chat_id TEXT NOT NULL,
                message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()


def allowed_chat(chat):
    if not CHAT_ID:
        return False

    # Numeric Telegram chat ID, including IDs beginning with -100
    if str(chat.get("id", "")) == CHAT_ID:
        return True

    # Public group/channel username, if configured as @username
    username = CHAT_ID.lstrip("@").lower()
    return bool(
        CHAT_ID.startswith("@")
        and chat.get("username", "").lower() == username
    )


def check_key():
    return bool(
        TEST_KEY
        and request.headers.get("X-Test-Key", "") == TEST_KEY
    )


@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Mogok Karaoke Backend"
    })


@app.route("/setup-webhook", methods=["POST"])
def setup_webhook():
    if not check_key():
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    if not BOT_TOKEN or not WEBHOOK_SECRET:
        return jsonify({
            "ok": False,
            "error": "Telegram bot or webhook secret is missing"
        }), 500

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", WEBHOOK_SECRET):
        return jsonify({
            "ok": False,
            "error": "Webhook secret must use letters, numbers, _ or -"
        }), 400

    base_url = request.host_url.rstrip("/")
    if not base_url.startswith("https://"):
        return jsonify({
            "ok": False,
            "error": "HTTPS is required"
        }), 400

    try:
        result = requests.post(
            telegram_api("setWebhook"),
            json={
                "url": base_url + "/telegram-webhook",
                "secret_token": WEBHOOK_SECRET,
                "allowed_updates": ["message", "channel_post"]
            },
            timeout=20
        )
        data = result.json()

        if result.ok and data.get("ok"):
            return jsonify({
                "ok": True,
                "message": "Telegram webhook configured"
            })

        return jsonify({
            "ok": False,
            "error": data.get("description", "Webhook setup failed")
        }), 502

    except requests.RequestException:
        return jsonify({
            "ok": False,
            "error": "Could not connect to Telegram"
        }), 502


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    supplied_secret = request.headers.get(
        "X-Telegram-Bot-Api-Secret-Token", ""
    )

    if not WEBHOOK_SECRET or supplied_secret != WEBHOOK_SECRET:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("channel_post")

    if not message:
        return jsonify({"ok": True})

    chat = message.get("chat", {})
    if not allowed_chat(chat):
        return jsonify({"ok": True, "ignored": True})

    # Regular Telegram video
    media = message.get("video")
    file_name = ""

    if media:
        file_name = media.get("file_name") or "video.mp4"
    else:
        # Also accept video files sent as documents
        document = message.get("document")
        if document and document.get("mime_type", "").startswith("video/"):
            media = document
            file_name = document.get("file_name") or "video.mp4"

    if not media or not media.get("file_id"):
        return jsonify({"ok": True})

    file_size = int(media.get("file_size") or 0)

    # Telegram cloud Bot API file downloads are limited to 20 MB.
    if file_size > 20 * 1024 * 1024:
        return jsonify({
            "ok": True,
            "ignored": True,
            "reason": "Video exceeds Telegram Bot API download limit"
        })

    try:
        with db_lock:
            with sqlite3.connect(DB_PATH) as db:
                db.execute("""
                    INSERT OR IGNORE INTO videos
                    (file_id, file_name, file_size, chat_id, message_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    media["file_id"],
                    file_name,
                    file_size,
                    str(chat.get("id", "")),
                    message.get("message_id")
                ))
                db.commit()

        return jsonify({"ok": True})

    except sqlite3.Error:
        app.logger.exception("Could not save video metadata")
        return jsonify({"ok": False}), 500


@app.route("/videos", methods=["GET"])
def list_videos():
    try:
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT id, file_name, file_size, created_at
                FROM videos
                ORDER BY id DESC
            """).fetchall()

        return jsonify({
            "ok": True,
            "videos": [dict(row) for row in rows]
        })

    except sqlite3.Error:
        app.logger.exception("Could not list videos")
        return jsonify({"ok": False, "error": "Database error"}), 500


@app.route("/download/<int:video_id>", methods=["GET"])
def download_video(video_id):
    if not BOT_TOKEN:
        return jsonify({
            "ok": False,
            "error": "Telegram bot token is not configured"
        }), 500

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        video = db.execute(
            "SELECT * FROM videos WHERE id = ?",
            (video_id,)
        ).fetchone()

    if not video:
        return jsonify({"ok": False, "error": "Video not found"}), 404

    try:
        file_info_response = requests.get(
            telegram_api("getFile"),
            params={"file_id": video["file_id"]},
            timeout=20
        )
        file_info = file_info_response.json()

        if not file_info_response.ok or not file_info.get("ok"):
            return jsonify({
                "ok": False,
                "error": "Telegram could not locate this video"
            }), 502

        file_path = file_info["result"].get("file_path")
        if not file_path:
            return jsonify({
                "ok": False,
                "error": "Telegram file path is missing"
            }), 502

        file_url = (
            f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        )
        upstream = requests.get(
            file_url,
            stream=True,
            timeout=(15, 60)
        )

        if not upstream.ok:
            upstream.close()
            return jsonify({
                "ok": False,
                "error": "Could not retrieve video from Telegram"
            }), 502

        filename = secure_filename(video["file_name"]) or "video.mp4"

        def stream_video():
            try:
                for chunk in upstream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        response = Response(
            stream_video(),
            content_type=upstream.headers.get(
                "Content-Type", "application/octet-stream"
            )
        )
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        response.headers["Cache-Control"] = "no-store"

        if upstream.headers.get("Content-Length"):
            response.headers["Content-Length"] = (
                upstream.headers["Content-Length"]
            )

        return response

    except requests.RequestException:
        app.logger.exception("Telegram download failed")
        return jsonify({
            "ok": False,
            "error": "Could not connect to Telegram"
        }), 502


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
