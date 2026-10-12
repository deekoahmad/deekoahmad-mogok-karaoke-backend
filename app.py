from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8957688388:AAENJ6-hXVIoWI-7dfDdlZIHLwLy7RMFfKE"
TELEGRAM_CHAT_ID = "@deeko_karaoki"

@app.route('/')
def home():
    return "Mogok Karaoke Backend is Running!"

@app.route('/download', methods=['GET'])
def download_video():
    youtube_url = request.args.get('url')
    file_name = request.args.get('name', 'karaoke_video')

    if not youtube_url:
        return "Error: YouTube URL is missing", 400

    try:
        # Cobalt API သုံးပြီး YouTube ဗီဒီယိုလင့်ခ်ကို တိုက်ရိုက် MP4 Link အဖြစ်ပြောင်းယူခြင်း
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": youtube_url,
            "vQuality": "720"
        }
        
        api_response = requests.post("https://co.wuk.sh/api/json", json=payload, headers=headers, timeout=20)
        res_data = api_response.json()

        if "url" in res_data:
            video_download_url = res_data["url"]
            
            # Telegram Group သို့ လင့်ခ်ပို့ပေးခြင်း (Backup)
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": f"📥 Downloaded: {file_name}\n{youtube_url}"},
                    timeout=10
                )
            except:
                pass

            # App ဘက်သို့ တိုက်ရိုက် Download ဆွဲရန် Video URL ကို JSON ဖြင့် ပြန်ပေးမည်
            return jsonify({
                "status": "success",
                "download_url": video_download_url,
                "file_name": file_name + ".mp4"
            })
        else:
            return f"API Error: {res_data}", 500

    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
