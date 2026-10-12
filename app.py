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
        cmd = [
            'yt-dlp',
            '--no-check-certificates',
            '-f', 'best',
            '-o', temp_filename,
            youtube_url
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0 or not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
            error_msg = result.stderr if result.stderr else "Unknown yt-dlp error"
            return f"Download Failed: {error_msg}", 500

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
