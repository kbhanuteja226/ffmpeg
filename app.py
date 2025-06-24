from flask import Flask, request, send_from_directory, jsonify
import os
import uuid
import requests
import subprocess
import threading

app = Flask(__name__)
OUTPUT_DIR = "videos"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_file(url, filename):
    response = requests.get(url)
    with open(filename, "wb") as f:
        f.write(response.content)

def generate_ffmpeg_video(image_url, audio_url, video_path, image_path, audio_path):
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
            video_path
        ]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"Error generating video: {e}")

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

    # Start processing in a background thread
    threading.Thread(target=generate_ffmpeg_video, args=(image_url, audio_url, output_path, image_path, audio_path)).start()

    return jsonify({
        "message": "Video is being processed. Check this URL after a few seconds.",
        "video_url": f"{request.host_url}videos/{uid}.mp4"
    })

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route('/')
def index():
    return "FFmpeg Async Microservice Running"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
