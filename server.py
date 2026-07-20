import http.server
import json
import os
import threading
import base64

# Render/Railway සඳහා dynamic port එකක් ලබා ගැනීමට os.environ භාවිතා කරයි.
# environment එකෙන් PORT එකක් නැත්නම් default 8000 ගනී.
PORT = int(os.environ.get("PORT", 8000))
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
        import time
        filename = f"{prefix}_{int(time.time()*1000)}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
        return f"/{UPLOAD_DIR}/{filename}"
    except Exception as e:
        print(f"❌ Media save error: {e}")
        return base64_data

class SecureDataHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        global refresh_counter
        if self.path.startswith("/api/check-refresh"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"refresh_counter": refresh_counter}).encode("utf-8"))
            return
        elif self.path.startswith("/api/data"):
            content = ""
            with file_lock:
                if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
                    try:
                        with open(DATA_FILE, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                    except Exception as e:
                        print(f"❌ Error reading data file: {e}")
            if not content:
                content = json.dumps({"title": "Learning Program", "subjects": [], "data_version": 1})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
            return
        else:
            # අනෙකුත් සියලුම static files (index.html වැනි) නිවැරදිව serve කිරීම
            super().do_GET()

    def do_POST(self):
        global refresh_counter
        if self.path == "/api/force-refresh":
            refresh_counter += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "triggered", "counter": refresh_counter}).encode("utf-8"))
            return
        elif self.path == "/api/data":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                incoming_json = json.loads(post_data.decode("utf-8"))
                
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "new_version": incoming_json["data_version"]}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.end_headers()

if __name__ == "__main__":
    # Render වලදී 0.0.0.0 මඟින් පිටතින් එන සබඳතා (incoming connections) විවෘත කරයි
    print(f"🚀 Production Server running at http://0.0.0.0:{PORT}")
    http.server.HTTPServer(("0.0.0.0", PORT), SecureDataHandler).serve_forever()