from flask import Flask, request, send_file
import subprocess
import os
import uuid

app = Flask(__name__)

@app.route('/')
def home():
    return "YouTube to MP4 Server is Running!"

@app.route('/download', methods=['GET'])
def download_video():
    youtube_url = request.args.get('url')
    file_name = request.args.get('name', 'karaoke_video')

    if not youtube_url:
        return "Error: YouTube URL is missing", 400

    temp_filename = f"{uuid.uuid4()}.mp4"
    
    try:
        # ffmpeg မလိုအပ်ဘဲ အကောင်းဆုံးရမည့် pre-merged format ဖြင့် temp ဖိုင်အဖြစ် ဒေါင်းမည်
        cmd = [
            'yt-dlp',
            '-f', 'best',
            '-o', temp_filename,
            youtube_url
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
            return "Error: Failed to download video", 500

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
            os.remove(temp_filename)
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
