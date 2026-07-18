# YouTube Downloader Pro

<div dir="rtl">

## تحميل فيديوهات يوتيوب بجودة عالية وواجهة احترافية

تطبيق ويب لتحميل فيديوهات وقوائم تشغيل يوتيوب بواجهة مستخدم مبهرة مع تتبع التقدم لحظياً ودعم اللغتين العربية والإنجليزية.

</div>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-green?logo=flask)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features / المميزات

- **HD Downloads** / تحميل بجودة عالية - Support for 360p to 4K quality
- **Audio Extraction** / استخراج الصوت - Convert to MP3 (192kbps)
- **Playlist Support** / دعم البلايليست - Download entire playlists with organized folders
- **Real-time Progress** / تتبع لحظي - Live progress via Server-Sent Events (SSE)
- **Bilingual UI** / واجهة ثنائية اللغة - Full Arabic & English support with RTL/LTR
- **Premium UI** / واجهة احترافية - Web Builders dark theme with glassmorphism
- **Responsive** / متجاوب - Works on desktop and mobile
- **Cross-platform** / متعدد المنصات - Windows, macOS, Linux

---

## Quick Start / البدء السريع

### Prerequisites / المتطلبات

- Python 3.10+
- ffmpeg (installed automatically via `install_ffmpeg.py`)

### Installation / التثبيت

```bash
# Clone the repository
git clone https://github.com/yourusername/youtube-downloader-pro.git
cd youtube-downloader-pro

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (optional - if not installed system-wide)
python install_ffmpeg.py

# Run the server
python app.py
```

Open http://localhost:5000 in your browser.

---

## Project Structure / هيكل المشروع

```
youtube-downloader-pro/
├── app.py                 # Flask backend server
├── downloader.py          # Core download logic (yt-dlp)
├── install_ffmpeg.py      # FFmpeg installer utility
├── requirements.txt       # Python dependencies
├── .gitignore             # Git ignore rules
├── LICENSE                # MIT License
├── README.md              # This file
├── static/
│   ├── index.html         # Frontend HTML (Bilingual)
│   ├── app.js             # Frontend JavaScript logic
│   ├── style.css          # Web Builders theme
│   ├── i18n.js            # Translation system (AR/EN)
│   └── wb-logo.svg        # Web Builders logo
└── downloads/             # Downloaded files (auto-created)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Serve frontend |
| GET | `/api/health` | Health check |
| POST | `/api/info` | Fetch video/playlist metadata |
| POST | `/api/download` | Start a download task |
| GET | `/api/progress/<id>` | Get task progress (JSON) |
| GET | `/api/stream/<id>` | SSE progress stream |
| GET | `/api/downloads` | List downloaded files |
| POST | `/api/open-folder` | Open downloads folder in OS |

---

## Built by / بناها

**[Web Builders](https://20057amo.github.io/webbuilders/)** - Building Ideas with Different Style.

<div dir="rtl">

### فريق Web Builders

| الاسم | الدور |
|-------|-------|
| Mahmoud Hamada | Software Engineer |
| Mahmoud M. Abdullah | Creative Director |
| Ahmed M. Ali | Leader (Development) |

</div>

---

## License

MIT License - See [LICENSE](LICENSE) for details.
