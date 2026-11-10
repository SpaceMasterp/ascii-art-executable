"""Run the loopback-only Code Art Studio with python -m codeart.app."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

from .contracts import Diagnostic, ErrorCode, GenerationRequest, GenerationResult, LayoutOptions, ShapeSpec
from .environment import environment_info, revision_info
from .pipeline import generate
from .prepass import inspect_file, selected_source
from .presentation import json_value
from .presentation import artifact_name, describe_result
from .verification_fixtures import BUILTIN_FIXTURES, select_builtin

WEB = Path(__file__).with_name("web")
MAX_BODY = 1024 * 1024
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/fonts/RobotoMono-Regular.ttf": ("fonts/RobotoMono-Regular.ttf", "font/ttf"),
}


def make_request(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    source = data.get("source", "")
    shape = data.get("shape", "circle")
    scale = data.get("scale", 1)
    sample = data.get("sample")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Enter a complete C11 function")
    if shape not in ("circle", "cat", "code"):
        raise ValueError("Choose circle, cat or CODE")
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or not 1 <= scale <= 4:
        raise ValueError("Initial scale must be between 1 and 4")
    if sample is not None and (not isinstance(sample, str) or sample not in BUILTIN_FIXTURES):
        raise ValueError("Unknown built-in sample")
    fixtures = select_builtin(sample) if sample else None
    # An edited sample becomes ordinary input. It cannot enter the execution stage.
    if fixtures and fixtures.fixture.source != source:
        fixtures = None
    return GenerationRequest(
        source, ShapeSpec(shape, "CODE" if shape == "code" else None),
        layout_options=LayoutOptions(initial_scale=scale), fixtures=fixtures,
    )


class Jobs:
    """Own one active generation and a bounded set of completed results."""

    def __init__(self, runner):
        self.runner = runner
        self.lock = Lock()
        self.items = {}
        self.active = None
        self.worker = None
        self.revision = revision_info()

    def submit(self, request, extraction=None):
        with self.lock:
            if self.active is not None:
                raise ValueError("A generation is already running. Finish or cancel it first.")
            while len(self.items) >= 5:
                del self.items[next(iter(self.items))]
            identifier = uuid4().hex
            job = {
                "id": identifier, "state": "running", "request": request, "prepass": extraction,
                "cancel": Event(), "result": None, "started": monotonic(), "elapsed_s": None,
            }
            self.items[identifier] = job
            self.active = identifier
        self.worker = Thread(target=self._run, args=(job,), daemon=True)
        self.worker.start()
        return identifier

    def _run(self, job):
        try:
            result = self.runner(job["request"], cancel_event=job["cancel"])
        except Exception as exc:
            result = GenerationResult(diagnostics=[
                Diagnostic(ErrorCode.INTERNAL_ERROR, "pipeline", f"{type(exc).__name__}: {exc}")
            ])
        with self.lock:
            job["result"] = result
            job["elapsed_s"] = monotonic() - job["started"]
            job["state"] = "finished"
            self.active = None

    def shutdown(self):
        with self.lock:
            for job in self.items.values():
                job["cancel"].set()
        if self.worker is not None:
            self.worker.join(timeout=35)

    def snapshot(self, identifier):
        with self.lock:
            job = self.items.get(identifier)
            if job is None:
                return None
            return {
                "id": identifier, "state": job["state"], "revision": self.revision,
                "elapsed_s": job["elapsed_s"],
                "source": job["request"].source_text,
                "shape": job["request"].shape_spec.kind,
                "scale": job["request"].layout_options.initial_scale,
                "sample": job["request"].fixtures.fixture.name if job["request"].fixtures else None,
                "result": ({**describe_result(job["result"]), "prepass": job["prepass"]} if job["result"] is not None else None),
            }

    def cancel(self, identifier):
        with self.lock:
            job = self.items.get(identifier)
            if job is None:
                return False
            job["cancel"].set()
            return True


def create_server(port=8765, *, runner=generate):
    jobs = Jobs(runner)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def respond(self, status, data, content_type="application/json; charset=utf-8", filename=None):
            body = json.dumps(data).encode("utf-8") if content_type.startswith("application/json") else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ASSETS:
                relative, content_type = ASSETS[path]
                self.respond(200, (WEB / relative).read_bytes(), content_type)
            elif path == "/api/samples":
                self.respond(200, [{"name": item.name, "source": item.source}
                                   for item in BUILTIN_FIXTURES.values()])
            elif path == "/api/environment":
                self.respond(200, environment_info())
            elif path.startswith("/api/jobs/"):
                parts = path.strip("/").split("/")
                if len(parts) < 3:
                    self.respond(404, {"error": "Unknown generation"})
                    return
                job = jobs.snapshot(parts[2])
                if job is None:
                    self.respond(404, {"error": "This result is unavailable. Run the generation again."})
                elif len(parts) == 3:
                    self.respond(200, job)
                elif len(parts) == 4 and parts[3] == "source.c" and job["result"] and job["result"]["source_text"]:
                    self.respond(200, job["result"]["source_text"].encode("utf-8"), "text/plain; charset=utf-8",
                                 artifact_name(job["sample"], job["shape"], job["result"]["layout"]))
                elif len(parts) == 4 and parts[3] == "report.json" and job["result"]:
                    self.respond(200, job, filename=artifact_name(job["sample"], job["shape"], job["result"]["layout"], "json"))
                else:
                    self.respond(404, {"error": "Download is not available yet"})
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{self.server.server_port}"
            if origin is not None and origin != expected:
                self.respond(403, {"error": "Open this page using its local server address"})
                return
            path = urlsplit(self.path).path
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and jobs.cancel(parts[2]):
                    self.respond(200, {"cancel_requested": True})
                else:
                    self.respond(404, {"error": "Unknown generation"})
                return
            if path not in ("/api/generate", "/api/prepass"):
                self.respond(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("Request must be between 1 byte and 1 MiB")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected JSON input")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                extraction = None
                if path == "/api/prepass" or data.get("file_mode"):
                    if not isinstance(data.get("source"), str):
                        raise ValueError("Expected source text")
                    extraction = inspect_file(data["source"], data.get("function"))
                    if path == "/api/prepass":
                        self.respond(200, json_value(extraction))
                        return
                    if extraction.error:
                        self.respond(400, {"error": extraction.error, "prepass": json_value(extraction)})
                        return
                    data["source"] = selected_source(extraction)
                    data["sample"] = None
                request = make_request(data)
                identifier = jobs.submit(request, json_value(extraction))
            except (ValueError, UnicodeError) as exc:
                self.respond(400, {"error": str(exc)})
                return
            self.respond(202, {"id": identifier})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.jobs = jobs
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = create_server(args.port)
    print(f"Code Art Studio: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.jobs.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
