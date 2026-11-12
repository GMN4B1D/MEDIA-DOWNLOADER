from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid
import re

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = tempfile.gettempdir()

FORMAT_MAP = {
    "none": "best",
    "original": "best",
    "mp4": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "webm": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
    "mp3": "bestaudio/best",
    "m4a": "bestaudio[ext=m4a]/bestaudio/best",
    "wav": "bestaudio/best",
    "ogg": "bestaudio/best",
    "flac": "bestaudio/best",
    "aac": "bestaudio/best",
}

AUDIO_POSTPROCESSORS = {
    "mp3": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
    "m4a": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}],
    "wav": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    "ogg": [{"key": "FFmpegExtractAudio", "preferredcodec": "vorbis", "preferredquality": "192"}],
    "flac": [{"key": "FFmpegExtractAudio", "preferredcodec": "flac"}],
    "aac": [{"key": "FFmpegExtractAudio", "preferredcodec": "aac", "preferredquality": "192"}],
}

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:100]

@app.route("/")
def home():
    return "Media Downloader Backend is Running!"

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    if not data or not data.get("url"):
        return jsonify({"error": "URL is required"}), 400

    url = data["url"].strip()
    fmt = (data.get("format") or "mp4").lower().strip()
    quality = data.get("quality", "best")

    if fmt not in FORMAT_MAP:
        fmt = "mp4"

    unique_id = str(uuid.uuid4())[:8]
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{unique_id}_%(title)s.%(ext)s")

    cookie_path = "cookie.txt"
    if not os.path.exists(cookie_path):
        cookie_path = "cookies.txt"

    # yt-dlp options optimized to bypass bot detection
    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "format": FORMAT_MAP[fmt],
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        # Force specific client combination to avoid sign-in wall
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-us,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        }
    }

    if os.path.exists(cookie_path):
        ydl_opts["cookiefile"] = cookie_path

    if fmt in AUDIO_POSTPROCESSORS:
        ydl_opts["postprocessors"] = AUDIO_POSTPROCESSORS[fmt]
        ydl_opts["format"] = "bestaudio/best"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = clean_filename(info.get("title", "video"))
            
            downloaded_file = None
            for file in os.listdir(DOWNLOAD_DIR):
                if file.startswith(unique_id):
                    downloaded_file = os.path.join(DOWNLOAD_DIR, file)
                    break

            if not downloaded_file or not os.path.exists(downloaded_file):
                return jsonify({"error": "Download failed – file not found"}), 500

            ext = os.path.splitext(downloaded_file)[1]
            final_name = f"{title}{ext}"

            return send_file(
                downloaded_file,
                as_attachment=True,
                download_name=final_name,
                    mimetype="application/octet-stream"
            )

    except Exception as e:
        err_msg = str(e)
        if "Sign in to confirm you're not a bot" in err_msg or "bot" in err_msg.lower():
            return jsonify({"error": "YouTube bot detection. cookies.txt আপডেট করুন।"}), 400
        return jsonify({"error": err_msg}), 500
    finally:
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(unique_id):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except:
                    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
