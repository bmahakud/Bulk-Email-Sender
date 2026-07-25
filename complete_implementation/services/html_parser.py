"""
HTML parsing and inline image conversion
"""
import base64
import re
from pathlib import Path
from typing import Tuple
from bs4 import BeautifulSoup
from loguru import logger


class HTMLParser:
    """Parse and process HTML content"""
    
    @staticmethod
    def convert_images_to_base64(html_content: str, base_path: Path) -> str:
        """
        Convert local image references to base64 inline images
        
        Args:
            html_content: HTML content with <img src="...">
            base_path: Base path for resolving relative image paths
            
        Returns:
            HTML with images converted to base64
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            
            # Skip if already base64
            if src.startswith('data:'):
                continue
            
            # Skip external URLs
            if src.startswith('http://') or src.startswith('https://'):
                continue
            
            # Convert local image to base64
            try:
                img_path = base_path / src if not Path(src).is_absolute() else Path(src)
                
                if img_path.exists():
                    with open(img_path, 'rb') as f:
                        img_data = f.read()
                    
                    # Detect image type
                    ext = img_path.suffix.lower()
                    mime_types = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.webp': 'image/webp',
                        '.svg': 'image/svg+xml'
                    }
                    mime_type = mime_types.get(ext, 'image/png')
                    
                    # Convert to base64
                    base64_data = base64.b64encode(img_data).decode('utf-8')
                    img['src'] = f"data:{mime_type};base64,{base64_data}"
                    
                    logger.info(f"Converted image to base64: {src}")
                else:
                    logger.warning(f"Image not found: {img_path}")
                    
            except Exception as e:
                logger.error(f"Error converting image {src}: {e}")
        
        return str(soup)
    
    @staticmethod
    def validate_html(html_content: str) -> Tuple[bool, str]:
        """
        Validate HTML content
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check if HTML is empty
            if not soup.get_text().strip():
                return False, "HTML content is empty"
            
            # Check for basic structure
            if not soup.find():
                return False, "Invalid HTML structure"
            
            return True, ""
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def extract_text_preview(html_content: str, max_length: int = 200) -> str:
        """Extract plain text preview from HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text().strip()
            if len(text) > max_length:
                text = text[:max_length] + "..."
            return text
        except:
            return ""
