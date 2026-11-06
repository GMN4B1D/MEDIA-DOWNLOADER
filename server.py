from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import re
from pathlib import Path

app = Flask(__name__)
CORS(app)

# FFmpeg path (Render এর জন্য দরকার)
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = None

AUDIO_FORMATS = {
    "mp3":  {"preferredcodec": "mp3",  "preferredquality": "192"},
    "m4a":  {"preferredcodec": "m4a",  "preferredquality": "192"},
    "wav":  {"preferredcodec": "wav"},
    "ogg":  {"preferredcodec": "vorbis", "preferredquality": "192"},
    "flac": {"preferredcodec": "flac"},
    "aac":  {"preferredcodec": "aac",  "preferredquality": "192"},
}

def clean_filename(name: str) -> str:
    name = name or "video"
    return re.sub(r'[\\/*?:"<>|]', "", name)[:100]

@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Media Downloader Backend Running"})

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "none").lower().strip()
    quality = (data.get("quality") or "best").lower().strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # Quality filter
    height = ""
    if quality == "1080":
        height = "[height<=1080]"
    elif quality == "720":
        height = "[height<=720]"
    elif quality == "480":
        height = "[height<=480]"

    # Format string
    if fmt in AUDIO_FORMATS:
        format_str = "bestaudio/best"
    elif fmt == "mp4":
        format_str = f"bestvideo{height}[ext=mp4]+bestaudio[ext=m4a]/bestvideo{height}+bestaudio/best[ext=mp4]/best"
    elif fmt == "webm":
        format_str = f"bestvideo{height}[ext=webm]+bestaudio/best[ext=webm]/best"
    else:
        format_str = f"bestvideo{height}+bestaudio/best{height}/best"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            outtmpl = str(tmp / "%(title).80s.%(ext)s")

            ydl_opts = {
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
                "format": format_str,
                "noplaylist": True,
                "retries": 5,
                "fragment_retries": 5,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["android", "ios", "mweb", "web"]
                    }
                },
            }

            # Cookies (সবচেয়ে জরুরি)
            if os.path.exists("cookies.txt"):
                ydl_opts["cookiefile"] = "cookies.txt"

            # FFmpeg
            if FFMPEG_PATH:
                ydl_opts["ffmpeg_location"] = FFMPEG_PATH

            # Audio convert
            if fmt in AUDIO_FORMATS:
                pp = {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": AUDIO_FORMATS[fmt]["preferredcodec"],
                }
                if "preferredquality" in AUDIO_FORMATS[fmt]:
                    pp["preferredquality"] = AUDIO_FORMATS[fmt]["preferredquality"]
                ydl_opts["postprocessors"] = [pp]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = clean_filename(info.get("title", "video"))

            files = list(tmp.glob("*"))
            if not files:
                return jsonify({"error": "Download failed. No file created."}), 500

            # সবচেয়ে বড় ফাইলটা নাও
            downloaded = max(files, key=lambda f: f.stat().st_size)
            ext = downloaded.suffix or ".mp4"
            final_name = f"{title}{ext}"

            return send_file(
                downloaded,
                as_attachment=True,
                download_name=final_name,
                mimetype="application/octet-stream",
            )

    except Exception as e:
        err = str(e)

        if "Sign in to confirm" in err or "not a bot" in err:
            return jsonify({
                "error": "YouTube bot detection. cookies.txt আপডেট করুন।"
            }), 403

        if "Private video" in err:
            return jsonify({"error": "এই ভিডিওটি প্রাইভেট।"}), 403

        if "Video unavailable" in err or "unavailable" in err.lower():
            return jsonify({"error": "ভিডিওটি পাওয়া যায়নি।"}), 404

        return jsonify({"error": err[:250]}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
