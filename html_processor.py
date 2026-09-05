import os
import hashlib
import aiofiles
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Comment, Tag
from playwright.async_api import Page
from structure_manager import StructureManager

class HtmlProcessor:
    def __init__(self, structure_manager: StructureManager, output_dir: Path):
        self.structure_manager = structure_manager
        self.output_dir = output_dir

    def make_relative_path(self, url: str, base_path: Path, current_url_netloc: str) -> str:
        """Convert absolute URL to relative path"""
        if url.startswith(('data:', 'blob:')):
            return url
        
        parsed = urlparse(url)
        if parsed.netloc and parsed.netloc != current_url_netloc:
            return url  # External URL, keep as is
        
        # Get local path
        local_path = self.structure_manager.get_local_path(url)
        
        # Calculate relative path from base_path
        try:
            relative = os.path.relpath(local_path, base_path.parent)
            # Normalize path separators for web
            return relative.replace('\\', '/')
        except ValueError:
            return url

    async def process_icons(self, soup: BeautifulSoup, main_html_path: Path):
        """Extract and process SVG icons"""
        svgs = soup.find_all('svg')
        for i, svg in enumerate(svgs):
            svg_str = str(svg)
            # Generate a filename for the SVG
            svg_hash = hashlib.md5(svg_str.encode()).hexdigest()[:8]
            svg_filename = f"icon_{svg_hash}.svg"
            svg_path = self.output_dir / "images" / svg_filename
            
            # Ensure images dir exists
            svg_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save SVG to file
            if not svg_str.strip().startswith('<?xml'):
                file_content = f'<?xml version="1.0" encoding="UTF-8"?>\n{svg_str}'
            else:
                file_content = svg_str
                
            async with aiofiles.open(svg_path, 'w', encoding='utf-8') as f:
                await f.write(file_content)
            
            # Calculate relative path
            try:
                relative_path = os.path.relpath(svg_path, main_html_path.parent)
                relative_path = relative_path.replace('\\', '/')
            except:
                relative_path = f"images/{svg_filename}"

            new_img = soup.new_tag("img", src=relative_path)
            # Copy classes and styles
            if svg.get('class'):
                new_img['class'] = svg['class']
            if svg.get('style'):
                new_img['style'] = svg['style']
            if svg.get('width'):
                new_img['width'] = svg['width']
            if svg.get('height'):
                new_img['height'] = svg['height']
            if svg.get('alt'):
                new_img['alt'] = svg['alt']
            else:
                new_img['alt'] = "icon"
            
            svg.replace_with(new_img)

    async def rewrite_html(self, page: Page, url: str, task_id: str, status_callback=None):
        """Rewrite HTML to use relative paths and clean up"""
        if status_callback:
            status_callback("processing", 85, "Rewriting and Cleaning HTML...")
        
        html_content = await page.content()
        
        # Get the main HTML file path
        main_html_path = self.structure_manager.get_local_path(url)
        
        soup = BeautifulSoup(html_content, 'lxml')
        current_netloc = urlparse(url).netloc

        # 1. Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. Extract Inline Styles - DISABLED for fidelity
        # style_tags = soup.find_all('style')
        # if style_tags:
        #     combined_css = ""
        #     for style in style_tags:
        #         if style.string:
        #             combined_css += style.string + "\n"
        #         style.extract()
            
        #     if combined_css.strip():
        #         css_filename = f"styles_{task_id[:8]}.css"
        #         css_path = self.output_dir / "css" / css_filename
        #         css_path.parent.mkdir(parents=True, exist_ok=True)
                
        #         async with aiofiles.open(css_path, 'w', encoding='utf-8') as f:
        #             await f.write(combined_css)
                
        #         new_link = soup.new_tag("link", rel="stylesheet", href=f"css/{css_filename}")
        #         if soup.head:
        #             soup.head.append(new_link)
        #         else:
        #             soup.body.insert(0, new_link)

        # 3. Extract Inline Scripts - DISABLED for fidelity
        # script_tags = soup.find_all('script')
        # combined_js = ""
        # for script in script_tags:
        #     if not script.get('src') and script.string:
        #         if script.get('type') == 'application/ld+json':
        #             continue 
                
        #         combined_js += script.string + "\n;\n"
        #         script.extract()
        
        # if combined_js.strip():
        #     js_filename = f"scripts_{task_id[:8]}.js"
        #     js_path = self.output_dir / "js" / js_filename
        #     js_path.parent.mkdir(parents=True, exist_ok=True)
            
        #     async with aiofiles.open(js_path, 'w', encoding='utf-8') as f:
        #         await f.write(combined_js)
            
        #     new_script = soup.new_tag("script", src=f"js/{js_filename}")
        #     if soup.body:
        #         soup.body.append(new_script)
        #     else:
        #         soup.append(new_script)

        # 4. Process Icons (SVG) - DISABLED for fidelity (keeps inline SVGs working with CSS)
        # await self.process_icons(soup, main_html_path)

        # 5. Extract Base64 Images
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src.startswith('data:image/'):
                try:
                    header, encoded = src.split(',', 1)
                    ext = header.split(';')[0].split('/')[1]
                    if ext == 'svg+xml': ext = 'svg'
                    
                    import base64
                    img_data = base64.b64decode(encoded)
                    
                    img_hash = hashlib.md5(encoded.encode()).hexdigest()[:8]
                    img_filename = f"img_{img_hash}.{ext}"
                    img_path = self.output_dir / "images" / img_filename
                    img_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    async with aiofiles.open(img_path, 'wb') as f:
                        await f.write(img_data)
                    
                    try:
                        relative_path = os.path.relpath(img_path, main_html_path.parent)
                        relative_path = relative_path.replace('\\', '/')
                    except:
                        relative_path = f"images/{img_filename}"
                    
                    img['src'] = relative_path
                except Exception as e:
                    print(f"Error extracting base64 image: {e}")

        # 6. List Truncation / Content Minimization - DISABLED to prevent breaking layout
        # for list_tag in soup.find_all(['ul', 'ol', 'div']):
        #     children = [c for c in list_tag.contents if isinstance(c, Tag)]
        #     if len(children) > 5:
        #         classes = [str(c.get('class')) for c in children]
        #         if len(set(classes)) == 1 and classes[0] != 'None':
        #             for child in children[3:]:
        #                 child.extract()
        #             comment = Comment(f" ... {len(children)-3} items removed for brevity ... ")
        #             list_tag.append(comment)

        # Process standard tags with URLs
        for tag in soup.find_all('link', href=True):
            tag['href'] = self.make_relative_path(tag['href'], main_html_path, current_netloc)

        for tag in soup.find_all(['script', 'img', 'audio', 'video', 'source', 'track', 'embed', 'iframe'], src=True):
            src = tag['src']
            if not src.startswith('data:'):
                tag['src'] = self.make_relative_path(src, main_html_path, current_netloc)
        
        # Handle poster attribute for video
        for tag in soup.find_all('video', poster=True):
            tag['poster'] = self.make_relative_path(tag['poster'], main_html_path, current_netloc)

        # Handle object data
        for tag in soup.find_all('object', data=True):
            tag['data'] = self.make_relative_path(tag['data'], main_html_path, current_netloc)
            
        # Handle srcset for img and source tags
        for tag in soup.find_all(['img', 'source'], srcset=True):
            if tag.get('srcset'):
                srcset = tag['srcset']
                new_srcset_parts = []
                for part in srcset.split(','):
                    parts = part.strip().split(' ', 1)
                    url = parts[0]
                    if not url.startswith('data:'):
                        new_url = self.make_relative_path(url, main_html_path, current_netloc)
                        if len(parts) > 1:
                            new_srcset_parts.append(f"{new_url} {parts[1]}")
                        else:
                            new_srcset_parts.append(new_url)
                tag['srcset'] = ", ".join(new_srcset_parts)

        # Remove Empty Attributes
        for tag in soup.find_all(True):
            attrs = list(tag.attrs.keys())
            for attr in attrs:
                if not tag[attr] and attr not in ['controls', 'autoplay', 'loop', 'checked', 'selected', 'disabled', 'readonly', 'required', 'multiple', 'ismap', 'defer', 'async']:
                     if tag[attr] == "":
                         del tag[attr]

        # Save rewritten HTML
        main_html_path.parent.mkdir(parents=True, exist_ok=True)
        final_html = soup.prettify()
        
        async with aiofiles.open(main_html_path, 'w', encoding='utf-8') as f:
            await f.write(final_html)
