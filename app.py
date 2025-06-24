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

def generate_slideshow_with_audio(image_urls, audio_url, video_path, uid):
    try:
        print(f"\n--- [START] Generating Video: {video_path} ---", flush=True)
        print(f"[INFO] Received {len(image_urls)} images and audio: {audio_url}", flush=True)

        image_paths = []
        images_txt_path = os.path.join(TEMP_DIR, f"{uid}_images.txt")
        audio_path = os.path.join(TEMP_DIR, f"{uid}_audio.mp3")

        # Download and save audio
        try:
            r = requests.get(audio_url)
            r.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(r.content)
            print(f"[Audio] Downloaded to: {audio_path}", flush=True)
        except Exception as e:
            print(f"[Audio ERROR] {e}", flush=True)
            return

        # Duration per image (10 min total)
        duration = 600 / len(image_urls)

        with open(images_txt_path, "w") as f:
            for idx, url in enumerate(image_urls):
                try:
                    print(f"[Image {idx+1}] Downloading: {url}", flush=True)
                    img_resp = requests.get(url)
                    img_resp.raise_for_status()
                    img = Image.open(BytesIO(img_resp.content)).convert("RGB")
                    img_path = os.path.join(TEMP_DIR, f"{uid}_img_{idx}.jpg")
                    img.save(img_path, "JPEG")
                    image_paths.append(img_path)
                    f.write(f"file '{img_path}'\n")
                    f.write(f"duration {duration}\n")
                    print(f"[Image {idx+1}] Saved as: {img_path}", flush=True)
                except Exception as e:
                    print(f"[Image {idx+1} ERROR] {e}", flush=True)

            if image_paths:
                f.write(f"file '{image_paths[-1]}'\n")  # Hold last image

        if not image_paths:
            print("[ERROR] No valid images were downloaded", flush=True)
            return

        # Build FFmpeg command
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

        print(f"[FFMPEG CMD] {' '.join(cmd)}", flush=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("[FFMPEG STDOUT]\n", result.stdout, flush=True)
        print("[FFMPEG STDERR]\n", result.stderr, flush=True)

        if os.path.exists(video_path):
            print(f"[✅ SUCCESS] Video created at {video_path}", flush=True)
        else:
            print(f"[❌ FAILURE] FFmpeg failed to create video", flush=True)

    except Exception as e:
        print(f"[EXCEPTION] {e}", flush=True)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    image_urls = data.get("image_urls")
    audio_url = data.get("audio_url")

    if not image_urls or not isinstance(image_urls, list) or not audio_url:
        return jsonify({"error": "Provide 'image_urls' (list) and 'audio_url' (string)."}), 400

    uid = str(uuid.uuid4())
    video_path = os.path.join(OUTPUT_DIR, f"{uid}.mp4")

    # Run video generation in background
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
    return "🎬 FFmpeg microservice is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
