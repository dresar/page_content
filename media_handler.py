import aiohttp
import aiofiles
import os
import re
from pathlib import Path
from urllib.parse import urljoin
from structure_manager import StructureManager

class MediaHandler:
    def __init__(self, session: aiohttp.ClientSession, structure_manager: StructureManager):
        self.session = session
        self.structure_manager = structure_manager
        self.downloaded_urls = set()

    async def download_file(self, url: str, file_path: Path) -> bool:
        """Download a file from URL to local path"""
        if url in self.downloaded_urls:
            return True
            
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    # Create directory if it doesn't exist
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    async with aiofiles.open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    
                    self.downloaded_urls.add(url)
                    return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False
        
        return False

    async def extract_css_assets(self, css_url: str, css_path: Path):
        """Extract assets referenced in CSS files (background images, fonts, etc.)"""
        if not css_path.exists():
            return
        
        try:
            async with aiofiles.open(css_path, 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Find all url() references
            url_pattern = r'url\s*\(\s*["\']?([^"\'()]+)["\']?\s*\)'
            urls = re.findall(url_pattern, content)
            
            replacements = {}
            
            for url in urls:
                # Skip data URIs
                if url.startswith('data:'):
                    continue
                
                # Make absolute URL
                if not url.startswith(('http://', 'https://')):
                    absolute_url = urljoin(css_url, url)
                else:
                    absolute_url = url
                
                if self.structure_manager.is_same_domain(absolute_url):
                    local_path = self.structure_manager.get_local_path(absolute_url)
                    await self.download_file(absolute_url, local_path)
                    
                    # Calculate relative path from CSS file to asset
                    try:
                        relative_path = os.path.relpath(local_path, css_path.parent)
                        relative_path = relative_path.replace('\\', '/')
                        replacements[url] = relative_path
                    except Exception as e:
                        print(f"Error calculating relative path: {e}")

            # Rewrite CSS content
            if replacements:
                for url, new_path in replacements.items():
                    safe_url = re.escape(url)
                    content = content.replace(url, new_path)
                
                async with aiofiles.open(css_path, 'w', encoding='utf-8') as f:
                    await f.write(content)

        except Exception as e:
            print(f"Error extracting CSS assets from {css_path}: {e}")

    async def check_and_download_fonts(self, font_urls: list, base_url: str):
        """Check and download font files"""
        print(f"Checking {len(font_urls)} fonts...")
        for font_url in font_urls:
            if not font_url.startswith(('http://', 'https://', 'data:', 'blob:')):
                font_url = urljoin(base_url, font_url)
            
            if self.structure_manager.is_same_domain(font_url) and not font_url.startswith(('data:', 'blob:')):
                local_path = self.structure_manager.get_local_path(font_url)
                # Extra check to ensure it goes to fonts folder (already handled by StructureManager but good for verification)
                if 'fonts' in str(local_path):
                    await self.download_file(font_url, local_path)

    async def check_and_download_music(self, music_urls: list, base_url: str):
        """Check and download music files"""
        print(f"Checking {len(music_urls)} music files...")
        for music_url in music_urls:
            if not music_url.startswith(('http://', 'https://', 'data:', 'blob:')):
                music_url = urljoin(base_url, music_url)
            
            if self.structure_manager.is_same_domain(music_url) and not music_url.startswith(('data:', 'blob:')):
                local_path = self.structure_manager.get_local_path(music_url)
                if 'music' in str(local_path):
                    await self.download_file(music_url, local_path)
