import os
import sqlite3
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = (
    os.environ.get("TELEGRAM_TARGET_CHAT_ID")
    or os.environ.get("TELEGRAM_GROUP_ID")
)
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
DB_PATH = os.environ.get("DB_PATH", "/tmp/mogok_videos.db")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            size INTEGER DEFAULT 0
        )
    """)
    return conn

def api(method, **kwargs):
    if not BOT_TOKEN:
        raise RuntimeError("Telegram token missing")
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        json=kwargs,
        timeout=30
    )
    r.raise_for_status()
    result = r.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram API request failed")
    return result["result"]

@app.get("/")
@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/telegram-webhook")
def telegram_webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if supplied != WEBHOOK_SECRET:
            return jsonify({"ok": False}), 403

    data = request.get_json(silent=True) or {}
    msg = data.get("message") or data.get("channel_post")

    if not msg:
        return jsonify({"ok": True})

    chat = msg.get("chat", {})
    if CHAT_ID and str(chat.get("id")) != str(CHAT_ID):
        return jsonify({"ok": True})

    media = msg.get("video") or msg.get("document")
    if not media:
        return jsonify({"ok": True})

    mime = media.get("mime_type", "")
    if "video" not in media and not mime.startswith("video/"):
        return jsonify({"ok": True})

    file_id = media.get("file_id")
    if not file_id:
        return jsonify({"ok": True})

    name = media.get("file_name") or "telegram_video.mp4"
    size = media.get("file_size") or 0

    conn = db()
    conn.execute(
        """INSERT INTO videos(file_id,name,size)
           VALUES(?,?,?)
           ON CONFLICT(file_id) DO UPDATE SET
           name=excluded.name,size=excluded.size""",
        (file_id, name, size)
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

@app.get("/videos")
def videos():
    conn = db()
    rows = conn.execute(
        "SELECT id,name,size FROM videos ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify({
        "videos": [dict(row) for row in rows]
    })

@app.get("/download/<int:video_id>")
def download_video(video_id):
    conn = db()
    row = conn.execute(
        "SELECT file_id,name FROM videos WHERE id=?",
        (video_id,)
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Video not found"}), 404

    try:
        info = api("getFile", file_id=row["file_id"])
        path = info.get("file_path")
        if not path:
            return jsonify({"error": "Telegram file unavailable"}), 502

        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
        upstream = requests.get(url, stream=True, timeout=(15, 60))
        if upstream.status_code != 200:
            upstream.close()
            return jsonify({"error": "Telegram download failed"}), 502

        filename = row["name"].replace("\r", "").replace("\n", "")
        filename = filename.replace('"', "")
        headers = {
            "Content-Disposition":
                f'attachment; filename="{filename}"',
            "Cache-Control": "no-store"
        }
        if upstream.headers.get("Content-Length"):
            headers["Content-Length"] = upstream.headers["Content-Length"]

        def stream():
            try:
                for chunk in upstream.iter_content(64 * 1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(
            stream(),
            headers=headers,
            content_type=upstream.headers.get(
                "Content-Type", "application/octet-stream"
            )
        )
    except Exception:
        app.logger.exception("Video download failed")
        return jsonify({"error": "Could not retrieve Telegram video"}), 502

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
