# Web Cloner Tool

A Python-based web cloner tool similar to saveweb2zip that allows you to download entire websites as portable ZIP files.

## Features

- 🚀 FastAPI web server with modern UI
- 🎭 Playwright-based crawling with full JavaScript rendering
- 📦 Automatic asset downloading (CSS, JS, Images, Fonts)
- 🔗 Relative path rewriting for offline use
- 📥 ZIP file compression
- 🧹 Automatic cleanup of temporary files
- 📊 Real-time progress tracking

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install chromium
```

## Usage

1. Start the server:
```bash
python main.py
```

2. Open your browser and navigate to:
```
http://localhost:8000
```

3. Enter a website URL and click "Clone Website"

4. Wait for the cloning process to complete

5. Download the ZIP file when ready

6. Extract the ZIP file and open the HTML files in your browser

## Technical Details

- **Backend**: FastAPI with async/await support
- **Frontend**: Jinja2 templates with vanilla JavaScript
- **Crawler**: Playwright (Chromium) for full JavaScript rendering
- **Asset Download**: aiohttp for async HTTP requests
- **Compression**: zipfile library for ZIP creation

## Project Structure

```
.
├── main.py              # FastAPI application
├── templates/
│   └── index.html       # Frontend UI
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Notes

- The tool only downloads assets from the same domain by default
- Temporary files are stored in the system temp directory
- Cleanup function removes temporary files after download
- Large websites may take some time to clone

