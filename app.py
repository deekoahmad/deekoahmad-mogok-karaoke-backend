from flask import Flask, request, send_file
import subprocess
import os
import uuid
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

    # yt-dlp ကို လိုအပ်ပါက အမြշတမ်း Update တင်မည်
    try:
        subprocess.run(['pip', 'install', '--upgrade', 'yt-dlp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

    temp_filename = f"{uuid.uuid4()}.mp4"
    
    try:
        # yt-dlp ဖြင့် ဗီဒီယိုဆွဲထုတ်ခြင်း (Android Client နှင့် Browser emulation သုံးမည်)
        cmd = [
            'yt-dlp',
            '--no-check-certificates',
            '--extractor-args', 'youtube:player_client=android,web',
            '-f', 'best[ext=mp4]/best',
            '-o', temp_filename,
            youtube_url
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0 or not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
            return f"Download Failed: {result.stderr}", 500

        # Telegram Group သို့ ဗီဒီယိုဖိုင် ပို့ပေးခြင်း (Backup အနေဖြင့်)
        try:
            with open(temp_filename, 'rb') as video_file:
                files = {'video': video_file}
                data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': f"📥 Downloaded: {file_name}"}
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo", data=data, files=files, timeout=30)
        except:
            pass

        safe_filename = f"{file_name}.mp4"

        response = send_file(
            temp_filename,
            as_attachment=True,
            download_name=safe_filename,
            mimetype='video/mp4'
        )
        return response

    except Exception as e:
        if os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
