import os
import shutil
import zipfile
import tempfile
import asyncio
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional
import uuid

from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright, Page
import aiohttp

# Import new modules
from structure_manager import StructureManager
from media_handler import MediaHandler
from html_processor import HtmlProcessor

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Store download status
download_status = {}


class WebCloner:
    def __init__(self, url: str, output_dir: Path, task_id: str):
        self.url = url
        self.output_dir = output_dir
        self.task_id = task_id
        self.parsed_url = urlparse(url)
        self.base_url = f"{self.parsed_url.scheme}://{self.parsed_url.netloc}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.page_title = "website"
        
        # Initialize managers
        self.structure_manager = StructureManager(self.url, self.base_url, output_dir)
        self.media_handler: Optional[MediaHandler] = None
        self.html_processor = HtmlProcessor(self.structure_manager, output_dir)
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        self.media_handler = MediaHandler(self.session, self.structure_manager)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def update_status(self, status: str, progress: int = 0, message: str = "", stats: dict = None):
        """Update download status"""
        current_status = download_status.get(self.task_id, {})
        
        # Merge stats with existing stats if provided
        existing_stats = current_status.get("stats", {})
        if stats:
            existing_stats.update(stats)
            
        download_status[self.task_id] = {
            "status": status,  # "processing", "completed", "error"
            "progress": progress,
            "message": message,
            "stats": existing_stats
        }
    
    async def extract_assets(self, page: Page):
        """Extract and download all assets from the page"""
        self.update_status("processing", 10, "Extracting assets...")
        
        # Get all resource URLs
        assets = await page.evaluate("""
            () => {
                const assets = {
                    css: [],
                    js: [],
                    images: [],
                    fonts: [],
                    music: []
                };
                
                // CSS files
                document.querySelectorAll('link[rel="stylesheet"]').forEach(link => {
                    if (link.href) assets.css.push(link.href);
                });
                
                // Inline styles with @import
                document.querySelectorAll('style').forEach(style => {
                    const text = style.textContent || '';
                    const imports = text.match(/@import\\s+['"]([^'"]+)['"]/g);
                    if (imports) {
                        imports.forEach(imp => {
                            const url = imp.match(/['"]([^'"]+)['"]/)[1];
                            assets.css.push(url);
                        });
                    }
                });
                
                // JS files
                document.querySelectorAll('script[src]').forEach(script => {
                    if (script.src) assets.js.push(script.src);
                });
                
                // Images
                document.querySelectorAll('img[src], img[srcset]').forEach(img => {
                    if (img.src) assets.images.push(img.src);
                    if (img.srcset) {
                        img.srcset.split(',').forEach(src => {
                            const url = src.trim().split(' ')[0];
                            if (url) assets.images.push(url);
                        });
                    }
                });
                
                // Background images from inline styles
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const bgImage = style.backgroundImage;
                    if (bgImage && bgImage !== 'none') {
                        const match = bgImage.match(/url\\(['"]?([^'")]+)['"]?\\)/);
                        if (match) assets.images.push(match[1]);
                    }
                });
                
                // Fonts
                document.querySelectorAll('link[rel*="font"], link[href*=".woff"], link[href*=".woff2"], link[href*=".ttf"], link[href*=".otf"]').forEach(link => {
                    if (link.href) assets.fonts.push(link.href);
                });

                // Music/Audio
                document.querySelectorAll('audio, source').forEach(el => {
                    if (el.src && el.src.match(/\\.(mp3|wav|ogg|m4a|aac|flac)$/i)) {
                        assets.music.push(el.src);
                    }
                });
                document.querySelectorAll('a[href$=".mp3"], a[href$=".wav"], a[href$=".ogg"]').forEach(link => {
                    if (link.href) assets.music.push(link.href);
                });
                
                return assets;
            }
        """)
        
        # Calculate stats
        stats = {
            "css": len(assets['css']),
            "js": len(assets['js']),
            "images": len(assets['images']),
            "fonts": len(assets['fonts']),
            "music": len(assets['music'])
        }
        
        # Download CSS files
        self.update_status("processing", 20, f"Downloading {len(assets['css'])} CSS files...", stats)
        for css_url in assets['css']:
            if not css_url.startswith(('http://', 'https://', 'data:', 'blob:')):
                from urllib.parse import urljoin
                css_url = urljoin(self.base_url, css_url)
            
            if self.structure_manager.is_same_domain(css_url) and not css_url.startswith(('data:', 'blob:')):
                local_path = self.structure_manager.get_local_path(css_url)
                await self.media_handler.download_file(css_url, local_path)
                # Also extract assets from CSS
                await self.media_handler.extract_css_assets(css_url, local_path)
        
        # Download JS files
        self.update_status("processing", 40, f"Downloading {len(assets['js'])} JS files...")
        for js_url in assets['js']:
            if not js_url.startswith(('http://', 'https://', 'data:', 'blob:')):
                from urllib.parse import urljoin
                js_url = urljoin(self.base_url, js_url)
            
            if self.structure_manager.is_same_domain(js_url) and not js_url.startswith(('data:', 'blob:')):
                local_path = self.structure_manager.get_local_path(js_url)
                await self.media_handler.download_file(js_url, local_path)
        
        # Download images
        self.update_status("processing", 60, f"Downloading {len(assets['images'])} images...")
        for img_url in assets['images']:
            if not img_url.startswith(('http://', 'https://', 'data:', 'blob:')):
                from urllib.parse import urljoin
                img_url = urljoin(self.base_url, img_url)
            
            if self.structure_manager.is_same_domain(img_url) and not img_url.startswith(('data:', 'blob:')):
                local_path = self.structure_manager.get_local_path(img_url)
                await self.media_handler.download_file(img_url, local_path)
        
        # Check and Download fonts
        self.update_status("processing", 80, f"Checking fonts...")
        await self.media_handler.check_and_download_fonts(assets['fonts'], self.base_url)

        # Check and Download music
        self.update_status("processing", 82, f"Checking music...")
        await self.media_handler.check_and_download_music(assets['music'], self.base_url)

    async def clone(self) -> Path:
        """Main cloning function"""
        try:
            self.update_status("processing", 5, "Initializing browser...")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                self.update_status("processing", 8, "Loading page...")
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                
                # Get page title for zip naming
                try:
                    self.page_title = await page.title()
                except:
                    pass
                
                # Wait for any dynamic content
                await asyncio.sleep(2)
                
                # Extract and download assets
                await self.extract_assets(page)
                
                # Rewrite HTML
                await self.html_processor.rewrite_html(page, self.url, self.task_id, self.update_status)
                
                await browser.close()
            
            self.update_status("processing", 90, "Creating ZIP file...")
            return self.output_dir
            
        except Exception as e:
            self.update_status("error", 0, str(e))
            raise


async def create_zip(output_dir: Path, zip_path: Path):
    """Create ZIP file from directory"""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(output_dir)
                zipf.write(file_path, arcname)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/clone")
async def clone_website(
    request: Request,
    background_tasks: BackgroundTasks,
    url: str = Form(...)
):
    """Start website cloning process"""
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Create temporary directory
    temp_dir = Path(tempfile.gettempdir()) / f"webclone_{task_id}"
    temp_dir.mkdir(exist_ok=True)
    
    # Initialize status
    download_status[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Starting..."
    }
    
    # Start cloning in background
    async def clone_task():
        try:
            async with WebCloner(url, temp_dir, task_id) as cloner:
                await cloner.clone()
                
                # Create ZIP file with website name
                import re
                clean_title = re.sub(r'[\\/*?:"<>|]', "", cloner.page_title)
                clean_title = clean_title.strip().replace(" ", "_")[:50]
                if not clean_title:
                    clean_title = f"webclone_{task_id}"
                else:
                    clean_title = f"{clean_title}_{task_id[:8]}"
                
                zip_filename = f"{clean_title}.zip"
                zip_path = temp_dir.parent / zip_filename
                
                await create_zip(temp_dir, zip_path)
                
                download_status[task_id] = {
                    "status": "completed",
                    "progress": 100,
                    "message": "Download ready!",
                    "zip_path": str(zip_path),
                    "zip_filename": zip_filename
                }
        except Exception as e:
            download_status[task_id] = {
                "status": "error",
                "progress": 0,
                "message": f"Error: {str(e)}"
            }
    
    asyncio.create_task(clone_task())
    
    return JSONResponse({"task_id": task_id})


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Get download status"""
    if task_id not in download_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JSONResponse(download_status[task_id])


@app.get("/download/{task_id}")
async def download_file(task_id: str):
    """Download the ZIP file"""
    if task_id not in download_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    status = download_status[task_id]
    if status["status"] != "completed":
        raise HTTPException(status_code=400, detail="Download not ready")
    
    zip_path = Path(status["zip_path"])
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=status["zip_filename"]
    )


@app.post("/cleanup/{task_id}")
async def cleanup(task_id: str, background_tasks: BackgroundTasks):
    """Clean up temporary files"""
    if task_id not in download_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    status = download_status[task_id]
    
    def cleanup_files():
        # Clean up temp directory
        temp_dir = Path(tempfile.gettempdir()) / f"webclone_{task_id}"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Clean up ZIP file
        if "zip_path" in status:
            zip_path = Path(status["zip_path"])
            if zip_path.exists():
                zip_path.unlink()
        
        # Remove from status
        if task_id in download_status:
            del download_status[task_id]
    
    background_tasks.add_task(cleanup_files)
    
    return JSONResponse({"message": "Cleanup scheduled"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
