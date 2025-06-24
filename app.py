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
        print(f"\n--- [START] Generating Video: {video_path} ---")

        image_paths = []
        images_txt_path = os.path.join(TEMP_DIR, f"{uid}_images.txt")
        audio_path = os.path.join(TEMP_DIR, f"{uid}_audio.mp3")

        # Download and save audio
        print(f"[Audio] Downloading: {audio_url}")
        r = requests.get(audio_url)
        r.raise_for_status()
        with open(audio_path, "wb") as f:
            f.write(r.content)
        print(f"[Audio] Saved to: {audio_path}")

        # Duration per image (600 seconds = 10 minutes)
        duration = 600 / len(image_urls)
        print(f"[INFO] Duration per image: {duration:.2f}s")

        with open(images_txt_path, "w") as f:
            for idx, url in enumerate(image_urls):
                print(f"\n[Image {idx+1}] Downloading: {url}")

                # Determine a temporary webp or png extension just for naming
                ext = url.split("?")[0].split(".")[-1].lower()
                temp_path = os.path.join(TEMP_DIR, f"{uid}_img_{idx}.{ext}")
                jpg_path = temp_path.replace(".webp", ".jpg").replace(".png", ".jpg")

                try:
                    img_resp = requests.get(url)
                    img_resp.raise_for_status()
                    img = Image.open(BytesIO(img_resp.content)).convert("RGB")
                    img.save(jpg_path, "JPEG")
                    print(f"[Image {idx+1}] Saved as: {jpg_path}")
                except Exception as e:
                    print(f"[ERROR] Failed to convert image {idx+1}: {e}")
                    continue

                if os.path.exists(jpg_path):
                    image_paths.append(jpg_path)
                    f.write(f"file '{jpg_path}'\n")
                    f.write(f"duration {duration}\n")
                else:
                    print(f"[WARNING] File does not exist: {jpg_path}")

            if image_paths:
                f.write(f"file '{image_paths[-1]}'\n")
            else:
                print("[ERROR] No valid images downloaded.")
                return

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

        print(f"\n[FFMPEG CMD] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("[FFMPEG STDOUT]\n", result.stdout)
        print("[FFMPEG STDERR]\n", result.stderr)

        if os.path.exists(video_path):
            print(f"[✅ SUCCESS] Video created at {video_path}")
        else:
            print(f"[❌ FAILURE] Video was not created")

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

    # Run generation in a separate thread
    thread = threading.Thread(
        target=generate_slideshow_with_audio,
        args=(image
