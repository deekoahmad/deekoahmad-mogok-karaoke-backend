import os
from flask import Flask, request
import telegram

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8957688388:AAENJ6-hXVIoWI-7dfDdlZIHLwLy7RMFfKE")
GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "@deeko_karaoki")

bot = telegram.Bot(token=BOT_TOKEN)

@app.route("/", methods=["GET"])
def home():
    return "Mogok Karaoke Forward Bot is running!"

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message") or data.get("edited_message")
        
        if message:
            text = message.get("text", "") or message.get("caption", "")
            
            if "youtube.com" in text or "youtu.be" in text:
                bot.send_message(
                    chat_id=GROUP_ID, 
                    text=f"🎵 New Link from App:\n{text}"
                )

    except Exception as e:
        print(f"Error: {e}")

    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
