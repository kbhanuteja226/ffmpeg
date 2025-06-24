from flask import Flask, request, send_from_directory, jsonify
import os
import uuid
import requests
import subprocess
import threading
from PIL import Image
from io import BytesIO

app = Flask(__name__)

OUTPUT_DIR = "videos"
TEMP_DIR = "temp"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Download file (handles webp to jpg)
def download_file(url, filename):
    try:
        print(f"[Downloading] {url}")
        r = requests.get(url, stream=True)
        r.raise_for_status()

        if filename.endswith(".webp"):
            # Convert to JPG
            image = Image.open(BytesIO(r.content)).convert("RGB")
            filename = filename.replace(".webp", ".jpg")
            image.save(filename, "JPEG")
        else:
            with open(filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        print(f"[Downloaded] {filename}")
        return filename
    except Exception as e:
        print(f"[Download Error] Failed to download {url}: {e}")
        raise

def generate_slideshow_with_audio(image_urls, audio_url, video_path, uid):
    try:
        print(f"\n--- Generating Video: {video_path} ---")
        image_paths = []
        images_txt_path = os.path.join(TEMP_DIR, f"{uid}_images.txt")
        audio_path = os.path.join(TEMP_DIR, f"{uid}_audio.mp3")

        # Download audio
        print(f"[Audio] Downloading: {audio_url}")
        download_file(audio_url, audio_path)

        # Duration per image (600 seconds = 10 minutes)
        duration = 600 / len(image_urls)
        print(f"[Info] Duration per image: {duration:.2f} sec")

        with open(images_txt_path, "w") as f:
            for idx, url in enumerate(image_urls):
                ext = url.split("?")[0].split(".")[-1].lower()
                img_path = os.path.join(TEMP_DIR, f"{uid}_img_{idx}.{ext}")
                actual_path = download_file(url, img_path)
                image_paths.append(actual_path)
                f.write(f"file '{actual_path}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file '{image_paths[-1]}'\n")  # repeat last frame

        # FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", images_txt_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            video_path
        ]

        print(f"[CMD] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("[FFMPEG STDOUT]\n", result.stdout)
        print("[FFMPEG STDERR]\n", result.stderr)

        if os.path.exists(video_path):
            print(f"[SUCCESS] ✅ Video created: {video_path}")
        else:
            print(f"[FAILURE] ❌ Video not found after FFmpeg")

    except Exception as e:
        print(f"[EXCEPTION] {e}")

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    image_urls = data.get("image_urls")
    audio_url = data.get("audio_url")

    if not image_urls or not isinstance(image_urls, list) or not audio_url:
        return jsonify({"error": "Provide 'image_urls' (list) and 'audio_url' (string)."}), 400

    uid = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f"{uid}.mp4")

    thread = threading.Thread(
        target=generate_slideshow_with_audio,
        args=(image_urls, audio_url, video_path, uid)
    )
    thread.start()

    return jsonify({
        "message": "Video generation started.",
        "video_url": f"{request.host_url}videos/{uid}.mp4"
    })

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/')
def home():
    return "🎬 FFmpeg 10-Minute Video Generator is running."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
