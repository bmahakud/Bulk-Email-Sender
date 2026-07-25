"""
HTML Renderer - Converts HTML content to images and PDFs using PySide6.
No external CLI tools or Webkit binaries are required.
"""
import base64
from pathlib import Path
from typing import Optional, Dict
from PySide6.QtGui import QTextDocument, QImage, QPainter, QPdfWriter, QPageSize
from PySide6.QtCore import QSize, Qt, QSizeF

class HTMLRenderer:
    """HTML to Image and PDF converter using PySide6 Qt GUI components"""
    
    @staticmethod
    def render_html_to_pdf(html_content: str, pdf_path: str, page_size_str: str = "A4") -> bool:
        """
        Render HTML content to a PDF file using QPdfWriter
        """
        try:
            doc = QTextDocument()
            doc.setHtml(html_content)
            
            # Map page size
            size_map = {
                "A4": QPageSize.A4,
                "Letter": QPageSize.Letter,
                "Legal": QPageSize.Legal
            }
            selected_size = size_map.get(page_size_str.upper(), QPageSize.A4)
            
            writer = QPdfWriter(pdf_path)
            writer.setPageSize(QPageSize(selected_size))
            
            # Print document to compiler pdf writer
            doc.print_(writer)
            return True
        except Exception as e:
            print(f"Error rendering HTML to PDF: {str(e)}")
            return False

    @staticmethod
    def render_html_to_image(html_content: str, image_path: str, format_str: str = "PNG", 
                              width_val: Optional[int] = None, height_val: Optional[int] = None) -> bool:
        """
        Render HTML content to an Image (PNG, JPEG, GIF, WEBP) using QPainter
        """
        try:
            doc = QTextDocument()
            doc.setHtml(html_content)
            
            # Page dimensions
            document_width = width_val if width_val and width_val > 0 else 800
            doc.setTextWidth(document_width)
            
            # Dynamically compute ideal height from document layout or use custom height
            document_height = height_val if height_val and height_val > 0 else int(doc.size().height())
            if document_height <= 0:
                document_height = 600
                
            image = QImage(QSize(document_width, document_height), QImage.Format_ARGB32)
            image.fill(Qt.white)  # Clear container with solid white background
            
            painter = QPainter(image)
            doc.drawContents(painter)
            painter.end()
            
            # Ensure output directory exists
            Path(image_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Save using selected format
            return image.save(image_path, format_str.upper())
        except Exception as e:
            print(f"Error rendering HTML to image: {str(e)}")
            return False

    @classmethod
    def render_html_to_base64_image(cls, html_content: str, format_str: str = "PNG",
                                    width_val: Optional[int] = None, height_val: Optional[int] = None) -> Optional[str]:
        """
        Render HTML input to a temporary image and return its base64 data URL
        """
        temp_img_path = str(Path("temp") / f"temp_body_render.{format_str.lower()}")
        if cls.render_html_to_image(html_content, temp_img_path, format_str, width_val, height_val):
            try:
                with open(temp_img_path, "rb") as f:
                    data = f.read()
                b64_data = base64.b64encode(data).decode("utf-8")
                mime = f"image/{format_str.lower()}"
                if format_str.lower() == "jpg":
                    mime = "image/jpeg"
                
                # Cleanup tempo file
                if Path(temp_img_path).exists():
                    Path(temp_img_path).unlink()
                
                return f"data:{mime};base64,{b64_data}"
            except Exception as e:
                print(f"Error converting rendered image to base64: {e}")
        return None

    @classmethod
    def render_html_to_base64_pdf(cls, html_content: str, page_size_str: str = "A4") -> Optional[str]:
        """
        Render HTML input to a temporary PDF and return its base64 bytes
        
        """
        temp_pdf = str(Path("temp") / "temp_attachment.pdf")
        if cls.render_html_to_pdf(html_content, temp_pdf, page_size_str):
            try:
                with open(temp_pdf, "rb") as f:
                    data = f.read()
                b64_data = base64.b64encode(data).decode("utf-8")
                
                # Cleanup
                if Path(temp_pdf).exists():
                    Path(temp_pdf).unlink()
                    
                return b64_data
            except Exception as e:
                print(f"Error reading rendered PDF to base64: {e}")
        return None
