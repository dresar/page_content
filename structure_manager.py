import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote

class StructureManager:
    def __init__(self, start_url: str, base_url: str, output_dir: Path):
        self.start_url = start_url
        self.base_url = base_url
        self.output_dir = output_dir
        self.parsed_base_url = urlparse(base_url)

    def get_local_path(self, url: str) -> Path:
        """Convert URL to local file path with flat structure"""
        # Handle main URL - ensure it maps to index.html at root
        if url == self.start_url or url.rstrip('/') == self.start_url.rstrip('/') or url == self.base_url or url.rstrip('/') == self.base_url.rstrip('/'):
             return self.output_dir / 'index.html'

        parsed = urlparse(url)
        path = unquote(parsed.path)
        ext = Path(path).suffix.lower()
        
        # Determine filename
        filename = Path(path).name
        if not filename:
            filename = "index.html"
            
        # Categorize into folders
        if ext in ['.css', '.less', '.scss']:
            folder = "css"
        elif ext in ['.js', '.mjs', '.jsx', '.ts', '.tsx']:
            folder = "js"
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.avif', '.bmp', '.tiff']:
            folder = "images"
        elif ext in ['.woff', '.woff2', '.ttf', '.otf', '.eot']:
            folder = "fonts"
        elif ext in ['.mp3', '.wav', '.ogg', '.m4a', '.aac', '.flac']:
            folder = "music"
        elif ext in ['.html', '.htm']:
            folder = "" # Keep HTMLs in root
        else:
            folder = "assets"

        # Handle long filenames and uniqueness
        name_obj = Path(filename)
        stem = name_obj.stem
        # If stem is too long, truncate
        if len(stem) > 30:
            stem = stem[:30]
            
        # Create hash from full URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # Detect SVG from URL/Query if filename doesn't show it
        if '.svg' in url.lower() and not ext:
            ext = '.svg'
            
        # Construct new filename
        new_filename = f"{stem}_{url_hash}{ext}"
        
        if folder:
            return self.output_dir / folder / new_filename
        else:
            return self.output_dir / new_filename

    def is_same_domain(self, url: str) -> bool:
        """Check if URL is from the same domain (including subdomains)"""
        parsed = urlparse(url)
        if not parsed.netloc:
            return True
            
        # Get root domains
        base_domain = '.'.join(self.parsed_base_url.netloc.split('.')[-2:])
        target_domain = '.'.join(parsed.netloc.split('.')[-2:])
        
        return base_domain == target_domain
