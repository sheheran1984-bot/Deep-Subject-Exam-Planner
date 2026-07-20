from flask import Flask, request, jsonify, send_from_directory
import json
import os
import threading
import base64
import time

app = Flask(__name__)

DATA_FILE = "quiz_data.json"
TEMP_FILE = "quiz_data.tmp"
UPLOAD_DIR = "uploads"

file_lock = threading.Lock()
refresh_counter = 0

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

# CORS Headers හැම Response එකකටම එකතු කරන්න (GitHub Pages එකෙන් කතා කරද්දී ඕන වෙනවා)
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/api/check-refresh', methods=['GET'])
def check_refresh():
    global refresh_counter
    return jsonify({"refresh_counter": refresh_counter})

@app.route('/api/data', methods=['GET'])
def get_data():
    content = ""
    with file_lock:
        if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except Exception as e:
                print(f"❌ Error reading data file: {e}")
    if not content:
        return jsonify({"title": "Learning Program", "subjects": [], "data_version": 1})
    return app.response_class(response=content, status=200, mimetype='application/json')

@app.route('/api/force-refresh', methods=['POST'])
def force_refresh():
    global refresh_counter
    refresh_counter += 1
    return jsonify({"status": "triggered", "counter": refresh_counter})

@app.route('/api/data', methods=['POST'])
def post_data():
    global refresh_counter
    try:
        incoming_json = request.get_json(force=True)
        
        for subject in incoming_json.get("subjects", []):
            for topic in subject.get("topics", []):
                for lesson in topic.get("lessons", []):
                    if lesson.get("videoData") and lesson["videoData"].startswith("data:"):
                        lesson["videoData"] = save_media_file(lesson["videoData"], "video")
                    for quiz in lesson.get("quizzes", []):
                        if quiz.get("image") and quiz["image"].startswith("data:"):
                            quiz["image"] = save_media_file(quiz["image"], "img")

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

# Upload කරපු පින්තූර සහ වීඩියෝ පිටතට පෙන්වීමට (Serve Media Files)
@app.route('/uploads/<filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=PORT)
