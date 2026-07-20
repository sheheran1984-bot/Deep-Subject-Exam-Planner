import os
import json
import threading
import base64
import time
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

# PythonAnywhere absolute paths
BASE_DIR = "/home/Sheheran1984/Deep-Subject-Exam-Planner"
DATA_FILE = os.path.join(BASE_DIR, "quiz_data.json")
TEMP_FILE = os.path.join(BASE_DIR, "quiz_data.tmp")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

file_lock = threading.Lock()
refresh_counter = 0

# Create uploads folder if missing
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def init_data_file():
    with file_lock:
        if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
            try:
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump({"title": "Learning Program", "subjects": [], "data_version": 1}, f, indent=4)
            except Exception as e:
                print(f"❌ Error initializing data file: {e}")

init_data_file()

def save_media_file(base64_data, prefix="file"):
    try:
        if not base64_data or not base64_data.startswith("data:"):
            return base64_data
            
        header, encoded = base64_data.split(",", 1)
        ext = header.split(";")[0].split("/")[1]
        filename = f"{prefix}_{int(time.time()*1000)}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
        return f"/uploads/{filename}"
    except Exception as e:
        print(f"❌ Media save error: {e}")
        return base64_data

# Serve the main HTML page
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# Serve uploaded images/videos
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)

# --- API ENDPOINTS ---

@app.route('/api/check-refresh', methods=['GET'])
def check_refresh():
    global refresh_counter
    return jsonify({"refresh_counter": refresh_counter})

@app.route('/api/data', methods=['GET'])
def get_data():
    content_data = None
    with file_lock:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content_data = json.load(f)
            except Exception as e:
                print(f"❌ Error reading data file: {e}")
                
    if content_data is None:
        content_data = {"title": "Learning Program", "subjects": [], "data_version": 1}
        
    return jsonify(content_data)

@app.route('/api/force-refresh', methods=['POST'])
def force_refresh():
    global refresh_counter
    refresh_counter += 1
    return jsonify({"status": "triggered", "counter": refresh_counter})

@app.route('/api/data', methods=['POST'])
def post_data():
    global refresh_counter
    try:
        incoming_json = request.json or {}
        
        # Save base64 media to files
        for subject in incoming_json.get("subjects", []):
            for topic in subject.get("topics", []):
                for lesson in topic.get("lessons", []):
                    if lesson.get("videoData") and lesson["videoData"].startswith("data:"):
                        lesson["videoData"] = save_media_file(lesson["videoData"], "video")
                    for quiz in lesson.get("quizzes", []):
                        if quiz.get("image") and quiz["image"].startswith("data:"):
                            quiz["image"] = save_media_file(quiz["image"], "img")

        # Write safely to JSON file
        with file_lock:
            server_version = 0
            if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        server_version = json.load(f).get("data_version", 0)
                except Exception:
                    server_version = 0
                    
            incoming_json["data_version"] = server_version + 1
            with open(TEMP_FILE, "w", encoding="utf-8") as f:
                json.dump(incoming_json, f, indent=4, ensure_ascii=False)
            os.replace(TEMP_FILE, DATA_FILE)
        
        refresh_counter += 1
        return jsonify({"status": "success", "new_version": incoming_json["data_version"]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# This is what PythonAnywhere looks for
application = app
