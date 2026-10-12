from flask import Flask, request, Response
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "YouTube to MP4 Streaming Server is Running!"

@app.route('/download', methods=['GET'])
def download_video():
    youtube_url = request.args.get('url')
    file_name = request.args.get('name', 'karaoke_video')

    if not youtube_url:
        return "Error: YouTube URL is missing", 400

    def generate():
        # yt-dlp ဖြင့် ဗီဒီယိုအပြည့်အစုံကို အကောင်းဆုံး format ဖြင့် stdout သို့ တိုက်ရိုက်ထုတ်ပေးခြင်း
        cmd = [
            'yt-dlp',
            '-f', 'best',
            '-o', '-',
            youtube_url
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        while True:
            data = process.stdout.read(65536)
            if not data:
                break
            yield data

    safe_filename = f"{file_name}.mp4".encode('utf-8').decode('latin-1')
    return Response(
        generate(),
        mimetype='video/mp4',
        headers={
            'Content-Disposition': f'attachment; filename="{safe_filename}"'
        }
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
