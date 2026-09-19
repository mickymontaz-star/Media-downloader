import os
import uuid
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, request, redirect, url_for, flash, sendfile, rendertemplatestring
import yt_dlp
import validators


app = Flask(_name_)
app.secretkey = os.environ.get("SECRETKEY", "change-this-secret")

DB = "media_history.db"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOADDIR, existok=True)


HTML = """
<!doctype html>
<html>
<head>
  <title>Media Downloader</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body{margin:0;font-family:Arial;background:#f3f4f6;color:#111827}
    nav{background:#111827;color:white;padding:16px;display:flex;justify-content:space-between}
    nav a{color:white;text-decoration:none;margin-left:14px;font-weight:bold}
    .wrap{max-width:850px;margin:25px auto;padding:0 14px}
    .card,.item{background:white;border-radius:14px;padding:20px;box-shadow:0 6px 18px #0001}
    h1{text-align:center;font-size:24px}
    input,select,button{width:100%;padding:14px;margin-top:12px;border-radius:10px;border:1px solid #d1d5db;font-size:16px;box-sizing:border-box}
    button{background:#2563eb;color:white;border:0;font-weight:bold}
    .check{display:flex;gap:8px;align-items:center;margin-top:12px}
    .check input{width:auto;margin:0}
    .msg{background:#fee2e2;color:#991b1b;padding:12px;border-radius:8px;margin-top:12px;word-break:break-word}
    .note,.meta,.url,.err{color:#6b7280;font-size:14px}
    .item{margin-bottom:12px}
    .title{font-weight:bold;margin-bottom:8px}
    .ok{color:#15803d;font-weight:bold}
    .bad{color:#dc2626;font-weight:bold}
    .link{display:inline-block;margin-top:10px;color:#2563eb;font-weight:bold;text-decoration:none}
    .url{word-break:break-all;margin-top:8px}
    .clear{background:#dc2626}
  </style>
</head>
<body>
<nav>
  <b>Media Downloader</b>
  <div>
    <a href="/">Home</a>
    <a href="/history">History</a>
  </div>
</nav>

<div class="wrap">

{% with messages = getflashedmessages() %}
  {% for m in messages %}
    <div class="msg">{{ m }}</div>
  {% endfor %}
{% endwith %}

{% if page == "home" %}
  <div class="card">
    <h1>Download by URL</h1>
    <form method="post">
      <input name="url" type="url" placeholder="Paste media URL" required>

      <select name="type">
        <option value="video">Video</option>
        <option value="audio">Audio MP3</option>
      </select>

      <select name="quality">
        <option value="best">Best quality</option>
        <option value="1080">1080p or lower</option>
        <option value="720">720p or lower</option>
        <option value="480">480p or lower</option>
        <option value="360">360p or lower</option>
      </select>

      <label class="check">
        <input type="checkbox" name="playlist">
        Allow playlist downloads
      </label>

      <button>Download</button>
    </form>
    <p class="note" style="text-align:center">No login. No rate limits.</p>
  </div>

  <h2>Recent downloads</h2>
{% else %}
  <div class="card">
    <h1>Download History</h1>
  </div>
{% endif %}

{% if downloads %}
  {% for d in downloads %}
    <div class="item">
      <div class="title">{{ d["title"] or "Unknown title" }}</div>
      <div class="meta">Type: {{ d["media_type"] }} | Quality: {{ d["quality"] }}</div>
      <div class="meta">Date: {{ d["downloaded_at"] }}</div>
      <div>
        Status:
        {% if d["status"] == "success" %}
          <span class="ok">Success</span>
        {% else %}
          <span class="bad">Failed</span>
        {% endif %}
      </div>

      {% if page == "history" %}
        <div class="url">{{ d["url"] }}</div>
      {% endif %}

      {% if d["error_message"] %}
        <div class="err">{{ d["error_message"] }}</div>
      {% endif %}

      {% if d["status"] == "success" %}
        <a class="link" href="/download/{{ d['id'] }}">Download again</a>
      {% endif %}
    </div>
  {% endfor %}

  {% if page == "history" %}
    <form method="post" action="/clear-history">
      <button class="clear">Clear History</button>
    </form>
  {% endif %}
{% else %}
  <p class="note" style="text-align:center">No downloads yet.</p>
{% endif %}

</div>
</body>
</html>
"""


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT,
            file_name TEXT,
            file_path TEXT,
            media_type TEXT,
            quality TEXT,
            status TEXT,
            error_message TEXT,
            downloaded_at TEXT
        )
    """)
    con.commit()
    con.close()


def savehistory(url, title, filename, filepath, mediatype, quality, status, error=None):
    con = db()
    con.execute("""
        INSERT INTO downloads
        (url,title,filename,filepath,mediatype,quality,status,errormessage,downloaded_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        url,
        title,
        file_name,
        file_path,
        media_type,
        quality,
        status,
        error,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    con.commit()
    con.close()


def history(limit=None):
    con = db()
    q = "SELECT * FROM downloads ORDER BY id DESC"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = con.execute(q).fetchall()
    con.close()
    return rows


def getdownload(downloadid):
    con = db()
    row = con.execute("SELECT * FROM downloads WHERE id=?", (download_id,)).fetchone()
    con.close()
    return row


def valid_url(url):
    if not url or not validators.url(url):
        return False
    p = urlparse(url)
    return p.scheme in ["http", "https"] and bool(p.netloc)


def ytdlpformat(mediatype, quality):
    if media_type == "audio":
        return "bestaudio/best"
    if quality == "1080":
        return "bestvideo[height<=1080]+bestaudio/best"
    if quality == "720":
        return "bestvideo[height<=720]+bestaudio/best"
    if quality == "480":
        return "bestvideo[height<=480]+bestaudio/best"
    if quality == "360":
        return "bestvideo[height<=360]+bestaudio/best"
    return "bestvideo+bestaudio/best"


def find_file(prefix):
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(prefix):
            return os.path.join(DOWNLOAD_DIR, f)
    return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url", "").strip()
        media_type = request.form.get("type", "video")
        quality = request.form.get("quality", "best")
        playlist = request.form.get("playlist") == "on"

        if not valid_url(url):
            flash("Invalid URL.")
            return redirect(url_for("index"))

        file_id = str(uuid.uuid4())

        opts = {
            "format": ytdlpformat(mediatype, quality),
            "outtmpl": os.path.join(DOWNLOADDIR, f"{fileid}.%(ext)s"),
            "noplaylist": not playlist,
            "mergeoutputformat": "mp4",
        }

        if media_type == "audio":
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "Unknown title")

            filepath = findfile(file_id)

            if not file_path:
                savehistory(url, title, None, None, mediatype, quality, "failed", "File was not created.")
                flash("Download failed. File was not created.")
                return redirect(url_for("index"))

            save_history(
                url,
                title,
                os.path.basename(file_path),
                file_path,
                media_type,
                quality,
                "success"
            )

            return sendfile(filepath, as_attachment=True)

        except Exception as e:
            savehistory(url, None, None, None, mediatype, quality, "failed", str(e))
            flash(str(e))
            return redirect(url_for("index"))

    return rendertemplatestring(HTML, page="home", downloads=history(8))


@app.route("/history")
def show_history():
    return rendertemplatestring(HTML, page="history", downloads=history())


@app.route("/download/<int:download_id>")
def downloadagain(downloadid):
    d = getdownload(downloadid)

    if not d:
        flash("Download record not found.")
        return redirect(urlfor("showhistory"))

    if not d["filepath"] or not os.path.exists(d["filepath"]):
        flash("File no longer exists.")
        return redirect(urlfor("showhistory"))

    return sendfile(d["filepath"], as_attachment=True)


@app.route("/clear-history", methods=["POST"])
def clear_history():
    con = db()
    con.execute("DELETE FROM downloads")
    con.commit()
    con.close()
    flash("History cleared.")
    return redirect(urlfor("showhistory"))


init_db()

if _name == "main_":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
