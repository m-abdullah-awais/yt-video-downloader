# YT Video Downloader

A fast, minimal, local web app for downloading YouTube videos and playlists. Paste a link in your browser, pick a quality, and the files are saved to the `output` folder of this project.

Built on [yt-dlp](https://github.com/yt-dlp/yt-dlp) with a tiny Python backend and a single HTML page. No accounts, no cloud, no tracking.

## Features

- Download single videos or complete playlists from one input field
- Quality choice: Best, 1080p, 720p, 480p, or MP3 audio
- MP4 output with H.264 video and AAC audio preferred, so files play everywhere
- Live progress with speed, time left, and playlist position
- Playlists are saved into their own folder with numbered file names
- Unavailable videos in a playlist are skipped instead of stopping the whole download
- Saved files list with size and date; click a file to play it in the browser
- One-click button to open the downloads folder
- Two downloads can run at the same time; more are queued automatically
- Fully portable: every dependency lives inside the project folder

## Requirements

- Windows 10 or 11
- An internet connection

That is all. `Setup.bat` reuses tools that are already installed on your computer and installs anything missing inside this project folder only. Nothing is installed globally.

| Tool | If already installed | If missing |
| --- | --- | --- |
| Python 3.10+ | Used as is | Portable Python downloaded into `runtime\python` |
| Node.js 20+ or Deno | Used as is | Deno installed into `.venv` |
| ffmpeg | Used as is | Local ffmpeg installed into `.venv` |
| Python packages (Flask, yt-dlp) | | Always installed into `.venv` |

## Getting started

1. Clone or download this repository.

   ```bash
   git clone <repository-url>
   ```

2. Double-click **`Setup.bat`**. This runs once and takes a minute or two.
3. Double-click **`Start.bat`**. The app opens in your browser at `http://127.0.0.1:5000`.
4. Paste a YouTube video or playlist link, choose a format, and click **Download**.

Downloaded files appear in the app and in the `output` folder. Close the Start.bat window (or press `Ctrl+C` in it) to stop the app.

## Keeping yt-dlp up to date

YouTube changes often. If downloads start failing, run `Setup.bat` again. It updates yt-dlp and the other packages to their latest versions without touching anything outside the project.

## Project structure

```
YT Video Downloader/
├── app.py              Backend: Flask server and yt-dlp download jobs
├── static/
│   └── index.html      Frontend: the whole UI in a single file
├── output/             Your downloaded videos and audio
├── requirements.txt    Python packages
├── Setup.bat           One-time setup, safe to run again
├── Start.bat           Starts the app and opens the browser
└── README.md
```

Created by `Setup.bat` and ignored by git:

- `.venv/` local Python environment with all packages
- `runtime/` portable Python, only when no Python was found on the system

## How it works

- `Start.bat` runs `app.py` with the project's own Python from `.venv`.
- The server listens on `127.0.0.1` only, so it cannot be reached from other devices.
- Each download becomes a job that runs yt-dlp in a background thread. The page polls `/api/jobs` once per second while something is downloading and stops polling when idle.
- Single videos are saved as `output/<title> [<id>].mp4`.
- Playlists are saved as `output/<playlist>/<number> - <title>.mp4`.
- Files that already exist are skipped, so running the same playlist again only fetches new videos.

### API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/download` | Start a download. Body: `{"url": "...", "format": "best"}`. Format is one of `best`, `1080`, `720`, `480`, `mp3` |
| `GET` | `/api/jobs` | Status and progress of all downloads in this session |
| `POST` | `/api/jobs/clear` | Remove finished and failed downloads from the list |
| `GET` | `/api/files` | Files in the `output` folder |
| `GET` | `/files/<path>` | Play or open a downloaded file |
| `POST` | `/api/open-folder` | Open the `output` folder in File Explorer |
| `GET` | `/api/status` | Detected tools and yt-dlp version |

## Troubleshooting

| Problem | Fix |
| --- | --- |
| "The app is not set up yet" | Run `Setup.bat` first |
| Downloads fail with a sign-in or format error | Run `Setup.bat` again to update yt-dlp |
| "ffmpeg was not found" | Run `Setup.bat` again, it installs a local copy |
| Port 5000 is busy | The app picks the next free port automatically and prints it in the Start.bat window |
| Setup fails while downloading | Check your internet connection and run `Setup.bat` again |

## Disclaimer

This tool is for personal use. Only download content you own or have permission to download, and respect YouTube's Terms of Service and the copyright of creators.

## Developer

**Muhammad Abdullah Awais**
Full Stack Developer

- Website: [www.abdullahawais.com](https://www.abdullahawais.com)
- Email: [contact@abdullahawais.com](mailto:contact@abdullahawais.com)
- LinkedIn: [m-abdullah-awais-programmer](https://www.linkedin.com/in/m-abdullah-awais-programmer)
- GitHub: [m-abdullah-awais](https://github.com/m-abdullah-awais)
- YouTube: [@m_abdullah_awais](https://www.youtube.com/@m_abdullah_awais)
- Instagram: [@m_abdullah_awais](https://www.instagram.com/m_abdullah_awais)
