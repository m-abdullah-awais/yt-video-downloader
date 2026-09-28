"""
YT Video Downloader

A small local web app that downloads YouTube videos and playlists with yt-dlp.
Paste a link in the browser, pick a quality, and the files land in ./output.

Developer: Muhammad Abdullah Awais (www.abdullahawais.com)
"""

import os
import re
import shutil
import socket
import sys
import threading
import time
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from flask import Flask, abort, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"

HOST = "127.0.0.1"
DEFAULT_PORT = 5000
MAX_PARALLEL_JOBS = 2

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mp3", ".m4a"}
YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "youtube-nocookie.com"}
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

SINGLE_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
PLAYLIST_TEMPLATE = "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s"

# Format choice -> (format selector, format sort). "res" is the smallest
# dimension, so vertical videos (Shorts) are capped correctly too. H.264 video
# and AAC audio are preferred so the MP4 plays everywhere without re-encoding.
VIDEO_FORMATS = {
    "best": ["res", "fps", "vcodec:h264", "acodec:m4a"],
    "1080": ["res:1080", "fps", "vcodec:h264", "acodec:m4a"],
    "720": ["res:720", "fps", "vcodec:h264", "acodec:m4a"],
    "480": ["res:480", "fps", "vcodec:h264", "acodec:m4a"],
}
FORMATS = set(VIDEO_FORMATS) | {"mp3"}


# ---------------------------------------------------------------------------
# External tools
# ---------------------------------------------------------------------------

def venv_executable(name):
    """Path to an executable inside the active virtual environment, if present."""
    candidate = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin") / name
    if os.name == "nt":
        candidate = candidate.with_suffix(".exe")
    return str(candidate) if candidate.is_file() else None


def find_ffmpeg():
    """Prefer a global ffmpeg, fall back to the local imageio-ffmpeg copy."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def find_js_runtimes():
    """JavaScript runtimes yt-dlp can use to solve YouTube challenges."""
    runtimes = {}
    deno = shutil.which("deno") or venv_executable("deno")
    if deno:
        runtimes["deno"] = {"path": deno}
    node = shutil.which("node")
    if node:
        runtimes["node"] = {"path": node}
    return runtimes


FFMPEG = find_ffmpeg()
JS_RUNTIMES = find_js_runtimes()


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

jobs = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_JOBS)


def update_job(job_id, **fields):
    with jobs_lock:
        jobs[job_id].update(fields)


def public_job(job):
    return {key: value for key, value in job.items() if not key.startswith("_")}


def clean_error(message):
    message = ANSI_ESCAPE.sub("", str(message)).strip()
    message = re.sub(r"^ERROR:\s*", "", message)
    message = re.sub(r"^\[[^\]]+\]\s*[\w-]+:\s*", "", message)
    return message or "Download failed."


class JobLogger:
    """Keeps yt-dlp quiet and remembers the last error for the job."""

    def __init__(self, job_id):
        self.job_id = job_id

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        with jobs_lock:
            job = jobs[self.job_id]
            job["_last_error"] = clean_error(message)
            job["_errors"] += 1


def normalize_url(raw):
    """Validate a YouTube link. Returns (url, single_video_only) or raises ValueError."""
    url = (raw or "").strip()
    if not url:
        raise ValueError("Please paste a YouTube link.")
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www.") or host.startswith("m."):
        host = host.split(".", 1)[1]
    if host.startswith("music."):
        host = host[len("music."):]
    if host not in YOUTUBE_HOSTS:
        raise ValueError("That does not look like a YouTube link.")

    # A video opened from a YouTube Mix (list=RD...) belongs to an endless
    # auto-generated list. Download just the video in that case.
    query = parse_qs(parsed.query)
    list_id = (query.get("list") or [""])[0]
    single_only = bool(query.get("v")) and list_id.startswith("RD")
    return url, single_only


def build_options(job_id, fmt, single_only):
    def on_progress(data):
        info = data.get("info_dict") or {}
        fields = {
            "index": info.get("playlist_index"),
            "total": info.get("n_entries") or info.get("playlist_count"),
            "item_title": info.get("title"),
        }
        if data.get("status") == "downloading":
            done = data.get("downloaded_bytes") or 0
            size = data.get("total_bytes") or data.get("total_bytes_estimate")
            fields.update(
                status="downloading",
                percent=round(done * 100 / size, 1) if size else None,
                speed=data.get("speed"),
                eta=data.get("eta"),
            )
        elif data.get("status") == "finished":
            fields.update(percent=100, speed=None, eta=0)
        update_job(job_id, **fields)

    def on_postprocess(data):
        if data.get("status") == "started":
            update_job(job_id, status="processing")

    def on_file_ready(path):
        with jobs_lock:
            jobs[job_id]["completed"] += 1

    options = {
        "paths": {"home": str(OUTPUT_DIR)},
        "outtmpl": SINGLE_TEMPLATE,
        "noplaylist": single_only,
        "ignoreerrors": True,
        "windowsfilenames": True,
        "trim_file_name": 150,
        "concurrent_fragment_downloads": 4,
        "retries": 10,
        "fragment_retries": 10,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "logger": JobLogger(job_id),
        "progress_hooks": [on_progress],
        "postprocessor_hooks": [on_postprocess],
        "post_hooks": [on_file_ready],
    }
    if FFMPEG:
        options["ffmpeg_location"] = FFMPEG
    if JS_RUNTIMES:
        options["js_runtimes"] = JS_RUNTIMES

    if fmt == "mp3":
        options["format"] = "ba/b"
        options["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        options["format"] = "bv*+ba/b"
        options["format_sort"] = VIDEO_FORMATS[fmt]
        options["merge_output_format"] = "mp4"
    return options


def run_job(job_id):
    with jobs_lock:
        job = jobs[job_id]
        url, fmt, single_only = job["url"], job["format"], job["_single_only"]
    update_job(job_id, status="starting")

    if not FFMPEG:
        update_job(job_id, status="error", error="ffmpeg was not found. Run Setup.bat and try again.")
        return

    try:
        with yt_dlp.YoutubeDL(build_options(job_id, fmt, single_only)) as ydl:
            # Resolve the link first so playlists get their own folder.
            info = ydl.extract_info(url, download=False, process=False)
            for _ in range(3):
                if not info or info.get("_type") != "url":
                    break
                info = ydl.extract_info(info["url"], download=False, process=False, ie_key=info.get("ie_key"))
            if info is None:
                raise yt_dlp.utils.DownloadError(jobs[job_id].get("_last_error") or "Could not read this link.")

            is_playlist = info.get("_type") in ("playlist", "multi_video")
            if is_playlist:
                ydl.params["outtmpl"]["default"] = PLAYLIST_TEMPLATE
            update_job(job_id, title=info.get("title") or url, playlist=is_playlist)

            ydl.process_ie_result(info, download=True)
    except Exception as exc:
        update_job(job_id, status="error", error=clean_error(exc), speed=None, eta=None)
        return

    with jobs_lock:
        job = jobs[job_id]
        completed = job["completed"]
        if job["playlist"] and job["total"]:
            failed = max(job["total"] - completed, 0)
        else:
            failed = 0 if completed else 1
        if completed == 0:
            job.update(status="error", error=job["_last_error"] or "Nothing was downloaded.", speed=None, eta=None)
        else:
            job.update(status="done", percent=100, speed=None, eta=None, failed=failed)
            if failed:
                job["error"] = f"{failed} item(s) could not be downloaded. {job['_last_error'] or ''}".strip()
        job["finished_at"] = time.time()


def create_job(url, fmt, single_only):
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "url": url,
        "format": fmt,
        "status": "queued",
        "title": None,
        "item_title": None,
        "playlist": False,
        "index": None,
        "total": None,
        "percent": None,
        "speed": None,
        "eta": None,
        "completed": 0,
        "failed": 0,
        "error": None,
        "created_at": time.time(),
        "finished_at": None,
        "_single_only": single_only,
        "_errors": 0,
        "_last_error": None,
    }
    with jobs_lock:
        jobs[job_id] = job
    executor.submit(run_job, job_id)
    return job_id


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.post("/api/download")
def api_download():
    payload = request.get_json(silent=True) or {}
    fmt = str(payload.get("format") or "best")
    if fmt not in FORMATS:
        return jsonify(error="Unknown format."), 400
    try:
        url, single_only = normalize_url(payload.get("url"))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    # Avoid starting the same download twice.
    with jobs_lock:
        for job in jobs.values():
            if job["url"] == url and job["format"] == fmt and job["status"] not in ("done", "error"):
                return jsonify(id=job["id"], duplicate=True)

    return jsonify(id=create_job(url, fmt, single_only)), 201


@app.get("/api/jobs")
def api_jobs():
    with jobs_lock:
        items = sorted((public_job(j) for j in jobs.values()), key=lambda j: j["created_at"], reverse=True)
    return jsonify(jobs=items)


@app.post("/api/jobs/clear")
def api_clear_jobs():
    with jobs_lock:
        for job_id in [k for k, j in jobs.items() if j["status"] in ("done", "error")]:
            del jobs[job_id]
    return jsonify(ok=True)


@app.get("/api/files")
def api_files():
    files = []
    if OUTPUT_DIR.is_dir():
        for path in OUTPUT_DIR.rglob("*"):
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
                stat = path.stat()
                relative = path.relative_to(OUTPUT_DIR).as_posix()
                files.append({
                    "name": path.name,
                    "path": relative,
                    "folder": path.parent.relative_to(OUTPUT_DIR).as_posix() if path.parent != OUTPUT_DIR else "",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
    files.sort(key=lambda f: f["modified"], reverse=True)
    return jsonify(files=files, total_size=sum(f["size"] for f in files))


@app.get("/files/<path:relative>")
def serve_file(relative):
    target = (OUTPUT_DIR / relative).resolve()
    if OUTPUT_DIR.resolve() not in target.parents or not target.is_file():
        abort(404)
    return send_from_directory(OUTPUT_DIR, relative)


@app.post("/api/open-folder")
def api_open_folder():
    OUTPUT_DIR.mkdir(exist_ok=True)
    try:
        if os.name == "nt":
            os.startfile(OUTPUT_DIR)
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(OUTPUT_DIR)])
    except OSError as exc:
        return jsonify(error=str(exc)), 500
    return jsonify(ok=True)


@app.get("/api/status")
def api_status():
    return jsonify(
        ffmpeg=bool(FFMPEG),
        js_runtime=next(iter(JS_RUNTIMES), None),
        yt_dlp=yt_dlp.version.__version__,
        output=str(OUTPUT_DIR),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def free_port(start):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((HOST, port)) != 0:
                return port
    raise RuntimeError("No free port found.")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    port = free_port(int(os.environ.get("PORT", DEFAULT_PORT)))
    url = f"http://{HOST}:{port}"

    print()
    print("  YT Video Downloader")
    print(f"  App:        {url}")
    print(f"  Downloads:  {OUTPUT_DIR}")
    print(f"  yt-dlp:     {yt_dlp.version.__version__}")
    print(f"  ffmpeg:     {FFMPEG or 'NOT FOUND (run Setup.bat)'}")
    print(f"  JS runtime: {', '.join(JS_RUNTIMES) or 'NOT FOUND (run Setup.bat)'}")
    print("  Press Ctrl+C to stop.")
    print()

    if "--open" in sys.argv:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()

    app.run(host=HOST, port=port, threaded=True, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
