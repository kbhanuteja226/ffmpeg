from flask import Flask, request, send_from_directory, jsonify
import os
import uuid
import requests
import subprocess
import threading

app = Flask(__name__)

OUTPUT_DIR = "videos"
TEMP_DIR = "temp"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def download_file(url, filename):
    try:
        print(f"[Downloading] {url}")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"[Downloaded] {filename}")
    except Exception as e:
        print(f"[Download Error] Failed to download {url}: {e}")
        raise

def generate_slideshow_with_audio(image_urls, audio_url, video_path, uid):
    try:
        image_paths = []
        images_txt_path = os.path.join(TEMP_DIR, f"{uid}_images.txt")
        audio_path = os.path.join(TEMP_DIR, f"{uid}_audio.mp3")

        # Download audio
        download_file(audio_url, audio_path)

        # Duration per image (so total = 600 seconds = 10 minutes)
        duration = 600 / len(image_urls)

        # Prepare images.txt file
        with open(images_txt_path, "w") as f:
            for idx, url in enumerate(image_urls):
                img_path = os.path.join(TEMP_DIR, f"{uid}_img_{idx}.jpg")
                download_file(url, img_path)
                image_paths.append(img_path)
                f.write(f"file '{img_path}'\n")
                f.write(f"duration {duration}\n")
            # Repeat last image
            f.write(f"file '{image_paths[-1]}'\n")

        # Run FFmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", images_txt_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-pix_fmt", "yuv420p",
            "-shortest",
            video_path
        ]

        print(f"[FFMPEG CMD] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("[FFMPEG OUTPUT]", result.stdout)
        print("[FFMPEG ERROR]", result.stderr)

        if os.path.exists(video_path):
            print(f"[SUCCESS] Video created at {video_path}")
        else:
            print(f"[FAILURE] Video NOT created")

    except Exception as e:
        print(f"[ERROR] {e}")

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    image_urls = data.get("image_urls")
    audio_url = data.get("audio_url")

    if not image_urls or not isinstance(image_urls, list) or not audio_url:
        return jsonify({"error": "Provide 'image_urls' (list) and 'audio_url' (string)."}), 400

    uid = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f"{uid}.mp4")

    # Process video in background thread
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
