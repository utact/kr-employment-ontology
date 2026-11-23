"""Serve only the viewer, at http://127.0.0.1:8765/view/."""

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import model

ROOT = Path(__file__).resolve().parent
MODEL_LOCK = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def local_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def json_response(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.local_host():
            self.send_error(403)
            return
        request_path = urlsplit(self.path).path
        if request_path == "/view/api/status":
            try:
                self.json_response(model.status())
            except ValueError as e:
                self.json_response({"error": str(e)}, 400)
            return
        if request_path in ("/", "/view"):
            self.send_response(302)
            self.send_header("Location", "/view/")
            self.end_headers()
            return
        decoded = unquote(request_path)
        if not decoded.startswith("/view/") or any(part.startswith(".") for part in decoded.split("/")):
            self.send_error(404)
            return
        self.path = request_path[len("/view"):]
        super().do_GET()

    def do_POST(self):
        if not self.local_host() or self.path != "/view/api/explain":
            self.send_error(404)
            return
        if self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
            self.json_response({"error": "뷰어 화면에서 요청해 주세요."}, 403)
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self.json_response({"error": "JSON 요청이 필요합니다."}, 415)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2048:
                raise ValueError("요청 크기를 확인해 주세요.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get("separationDate"), str):
                raise ValueError("이직일이 필요합니다.")
        except (ValueError, TypeError) as e:
            self.json_response({"error": str(e)}, 400)
            return
        if not MODEL_LOCK.acquire(blocking=False):
            self.json_response({"error": "다른 모델 요청이 진행 중입니다."}, 429)
            return
        streamed = "application/x-ndjson" in self.headers.get("Accept", "")
        def send_event(event):
            self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        if streamed:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
        try:
            if streamed:
                result = model.explain(payload["separationDate"], on_progress=lambda state: send_event({"type": "status", **state}))
                send_event({"type": "result", **result})
            else:
                self.json_response(model.explain(payload["separationDate"]))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except ValueError as e:
            if streamed:
                send_event({"type": "error", "error": str(e)})
            else:
                self.json_response({"error": str(e)}, 502)
        except Exception:
            # Provider bodies and exception representations can contain credentials.
            if streamed:
                send_event({"type": "error", "error": "모델 설명을 불러오지 못했습니다."})
            else:
                self.json_response({"error": "모델 설명을 불러오지 못했습니다."}, 500)
        finally:
            MODEL_LOCK.release()

    def do_HEAD(self):
        # No alternate route to repository files via HEAD.
        self.send_error(405)

    def list_directory(self, path):
        self.send_error(404)
        return None

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(ROOT)))
    print(f"Local: http://127.0.0.1:{args.port}/view/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
