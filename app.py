from flask import Flask, request, send_from_directory, jsonify
import os
import uuid
import requests
import subprocess

app = Flask(__name__)
OUTPUT_DIR = "videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_file(url, filename):
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)

@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.json
    image_url = data.get("image_url")
    audio_url = data.get("audio_url")

    if not image_url or not audio_url:
        return jsonify({"error": "Both image_url and audio_url are required."}), 400

    uid = str(uuid.uuid4())
    image_path = f"{uid}_image.jpg"
    audio_path = f"{uid}_audio.mp3"
    output_path = os.path.join(OUTPUT_DIR, f"{uid}.mp4")

    try:
        download_file(image_url, image_path)
        download_file(audio_url, audio_path)

        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            output_path
        ]
        subprocess.run(cmd, check=True)

        return jsonify({
            "video_url": f"{request.host_url}videos/{uid}.mp4"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Optional: Clean up image/audio if needed
        pass

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/')
def index():
    return "FFmpeg Video Microservice Running"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
