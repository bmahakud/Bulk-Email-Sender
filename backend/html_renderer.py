"""
HTML Renderer - Converts HTML content to images and PDFs using PySide6.
No external CLI tools or Webkit binaries are required.
"""
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple
import re
from PySide6.QtGui import (
    QTextDocument, QImage, QPainter, QPdfWriter, QPageSize, QPageLayout
)
from PySide6.QtCore import QSize, Qt, QSizeF, QMarginsF, QUrl, QRectF

PAGE_SIZE_DIMENSIONS_MM: Dict[str, Tuple[float, float]] = {
    "A0": (841.0, 1189.0),
    "A1": (594.0, 841.0),
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "LETTER": (215.9, 279.4),
    "LEGAL": (215.9, 355.6),
    "TABLOID": (279.4, 431.8),
    "LEDGER": (431.8, 279.4),
    "EXECUTIVE": (184.15, 266.7),
    "B4": (250.0, 353.0),
    "B5": (176.0, 250.0),
}

class HTMLRenderer:
    """HTML to Image and PDF converter using PySide6 Qt GUI components"""

    @staticmethod
    def _get_qpage_size(size_str: str, custom_dims_mm: Optional[Tuple[float, float]] = None) -> QPageSize:
        """Create a precise QPageSize object matching standard or custom dimensions."""
        if custom_dims_mm:
            w, h = custom_dims_mm
            return QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter)

        key = (size_str or "A4").upper()
        if key in PAGE_SIZE_DIMENSIONS_MM:
            w, h = PAGE_SIZE_DIMENSIONS_MM[key]
            enum_val = None
            if hasattr(QPageSize, "PageSizeId"):
                enum_name = key.capitalize() if key in ("LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE") else key
                enum_val = getattr(QPageSize.PageSizeId, enum_name, None)
            if enum_val is None:
                enum_name = key.capitalize() if key in ("LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE") else key
                enum_val = getattr(QPageSize, enum_name, None)

            if enum_val is not None:
                try:
                    return QPageSize(enum_val)
                except Exception:
                    pass
            return QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter)

        return QPageSize(QPageSize.PageSizeId.A4) if hasattr(QPageSize, "PageSizeId") else QPageSize(QPageSize.A4)

    @staticmethod
    def _parse_page_css(html_content: str):
        """
        Parses @page rules from CSS in the HTML content, extracting:
        - page_size_str: (A4, A1, A0, Letter, Legal, etc.)
        - is_landscape: bool
        - margins_mm: (top, right, bottom, left) in millimeters, or None
        - has_explicit_breaks: bool
        - explicit_breaks_count: int
        - custom_dims_mm: Optional[Tuple[float, float]]
        """
        page_size_str = "A4"
        is_landscape = False
        margins_mm = None
        custom_dims_mm = None

        break_matches = re.findall(
            r'page-break-(before|after):\s*always|break-(before|after):\s*page',
            html_content, re.IGNORECASE
        )
        has_explicit_breaks = bool(break_matches)
        explicit_breaks_count = len(break_matches)

        def _to_mm(val_str: str) -> float:
            val_str = val_str.strip()
            m = re.match(r'^([0-9.]+)\s*(mm|cm|in|px|pt)?$', val_str, re.IGNORECASE)
            if not m:
                return 0.0
            num = float(m.group(1))
            unit = (m.group(2) or "mm").lower()
            if unit == "mm": return num
            if unit == "cm": return num * 10.0
            if unit == "in": return num * 25.4
            if unit == "pt": return num * (25.4 / 72.0)
            if unit == "px": return num * (25.4 / 96.0)
            return num

        page_match = re.search(r'@page\s*\{([^}]+)\}', html_content, re.IGNORECASE | re.DOTALL)
        if page_match:
            block = page_match.group(1)

            if re.search(r'\blandscape\b', block, re.IGNORECASE):
                is_landscape = True
            elif re.search(r'\bportrait\b', block, re.IGNORECASE):
                is_landscape = False

            size_m = re.search(r'size:\s*([^;\}]+)', block, re.IGNORECASE)
            if size_m:
                size_val = size_m.group(1).strip()
                if re.search(r'\blandscape\b', size_val, re.IGNORECASE):
                    is_landscape = True
                elif re.search(r'\bportrait\b', size_val, re.IGNORECASE):
                    is_landscape = False

                for name in ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "LETTER", "LEGAL", "TABLOID", "LEDGER", "EXECUTIVE", "B4", "B5"):
                    if re.search(rf'\b{name}\b', size_val, re.IGNORECASE):
                        page_size_str = name
                        break

                dim_m = re.findall(r'([0-9.]+)\s*(mm|cm|in|px|pt)', size_val, re.IGNORECASE)
                if len(dim_m) >= 2:
                    custom_dims_mm = (_to_mm(f"{dim_m[0][0]}{dim_m[0][1]}"), _to_mm(f"{dim_m[1][0]}{dim_m[1][1]}"))

            margin_m = re.search(r'margin:\s*([^;\}]+)', block, re.IGNORECASE)
            if margin_m:
                raw_margin = margin_m.group(1).strip()
                parts = raw_margin.split()
                try:
                    mm_vals = [_to_mm(p) for p in parts if p.strip()]
                    if len(mm_vals) == 1:
                        margins_mm = (mm_vals[0], mm_vals[0], mm_vals[0], mm_vals[0])
                    elif len(mm_vals) == 2:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[0], mm_vals[1])
                    elif len(mm_vals) == 3:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[2], mm_vals[1])
                    elif len(mm_vals) >= 4:
                        margins_mm = (mm_vals[0], mm_vals[1], mm_vals[2], mm_vals[3])
                except Exception:
                    pass
        else:
            if re.search(r'594\s*mm|841\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A1"
            elif re.search(r'420\s*mm|594\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A2"
            elif re.search(r'297\s*mm|420\s*mm', html_content, re.IGNORECASE):
                page_size_str = "A3"

        return page_size_str, is_landscape, margins_mm, has_explicit_breaks, explicit_breaks_count, custom_dims_mm

    @staticmethod
    def _register_data_images(doc: QTextDocument, html_content: str):
        """Pre-register base64 data URIs as document resources so images always render."""
        data_uris = re.findall(
            r'src=["\'](data:image/([a-zA-Z0-9+.-]+);base64,([A-Za-z0-9+/=]+))["\']',
            html_content, re.IGNORECASE
        )
        for full_src, img_fmt, b64_str in data_uris:
            try:
                raw_bytes = base64.b64decode(b64_str)
                qimg = QImage.fromData(raw_bytes)
                if not qimg.isNull():
                    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(full_src), qimg)
            except Exception:
                pass

    @staticmethod
    def render_html_to_pdf(html_content: str, pdf_path: str, page_size_str: str = "A4") -> bool:
        """
        Render HTML content to a PDF file using QPdfWriter.
        Automatically honors @page CSS rules (A4, A1, Letter, orientation, margins)
        and guarantees multi-page or single-page templates strictly preserve their
        natural page count consistently across every recipient.
        """
        try:
            Path(pdf_path).parent.mkdir(parents=True, exist_ok=True)

            # 1. Parse @page rules from CSS
            css_size, is_landscape, margins_mm, has_explicit_breaks, explicit_breaks_count, custom_dims_mm = (
                HTMLRenderer._parse_page_css(html_content)
            )
            target_size_str = css_size if css_size else page_size_str

            # 2. Select precise page size
            selected_size = HTMLRenderer._get_qpage_size(target_size_str, custom_dims_mm)

            # 3. Setup QPdfWriter
            writer = QPdfWriter(pdf_path)
            writer.setPageSize(selected_size)
            writer.setResolution(96)

            orient = QPageLayout.Orientation.Landscape if is_landscape else QPageLayout.Orientation.Portrait
            writer.setPageOrientation(orient)

            # 4. Apply margins from @page or clean defaults
            if margins_mm is not None:
                top_m, right_m, bot_m, left_m = margins_mm
                writer.setPageMargins(QMarginsF(left_m, top_m, right_m, bot_m), QPageLayout.Unit.Millimeter)
            else:
                writer.setPageMargins(QMarginsF(8, 8, 8, 8), QPageLayout.Unit.Millimeter)

            # 5. Measure printable page pixel dimensions at 96 DPI
            try:
                paint_rect = writer.pageLayout().paintRectPixels(writer.resolution())
                page_w = paint_rect.width()
                page_h = paint_rect.height()
            except Exception:
                page_w = writer.width()
                page_h = writer.height()

            # 6. Load document & register base64 images
            doc = QTextDocument()
            HTMLRenderer._register_data_images(doc, html_content)
            doc.setHtml(html_content)
            doc.setTextWidth(page_w)

            # Measure continuous unpaginated document height
            natural_h = doc.size().height()
            natural_w = doc.idealWidth()

            # 7. Determine exact target page count
            min_pages = (explicit_breaks_count + 1) if has_explicit_breaks else 1

            if page_h > 0 and natural_h > 0:
                full_pages = int(natural_h // page_h)
                remainder = natural_h % page_h
                if remainder == 0:
                    computed_pages = max(1, full_pages)
                else:
                    # Tolerance: spillover up to 75px is absorbed into existing full_pages
                    if remainder <= 75.0 and full_pages >= 1:
                        computed_pages = full_pages
                    else:
                        computed_pages = full_pages + 1
            else:
                computed_pages = 1

            target_pages = max(computed_pages, min_pages)

            # 8. Calculate scaling to fit perfectly within target_pages without distortion
            total_target_h = target_pages * page_h
            scale_y = (total_target_h / natural_h) if (natural_h > total_target_h) else 1.0
            scale_x = (page_w / natural_w) if (natural_w > 0 and natural_w > page_w) else 1.0
            scale = min(scale_x, scale_y, 1.0)

            offset_x = 0.0
            if scale < 1.0:
                scaled_w = page_w * scale
                if page_w > scaled_w:
                    offset_x = (page_w - scaled_w) / 2.0

            # 9. Render pages with strict page count preservation
            if target_pages == 1:
                painter = QPainter(writer)
                if scale < 1.0:
                    if offset_x > 0:
                        painter.translate(offset_x, 0)
                    painter.scale(scale, scale)
                doc.drawContents(painter)
                painter.end()
                return True
            else:
                effective_page_h = page_h / scale
                doc.setPageSize(QSizeF(page_w / scale, effective_page_h))

                painter = QPainter(writer)
                for p in range(target_pages):
                    if p > 0:
                        writer.newPage()
                    painter.save()
                    if offset_x > 0:
                        painter.translate(offset_x, 0)
                    painter.scale(scale, scale)
                    painter.translate(0, -p * effective_page_h)
                    clip_rect = QRectF(0, p * effective_page_h, page_w / scale, effective_page_h)
                    painter.setClipRect(clip_rect)
                    doc.drawContents(painter, clip_rect)
                    painter.restore()
                painter.end()
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
            HTMLRenderer._register_data_images(doc, html_content)
            doc.setHtml(html_content)
            
            # Page dimensions
            if width_val and width_val > 0:
                document_width = width_val
            else:
                css_size, is_landscape, _, _, _, custom_dims = HTMLRenderer._parse_page_css(html_content)
                if custom_dims:
                    document_width = int(custom_dims[0] * 96 / 25.4)
                elif css_size in PAGE_SIZE_DIMENSIONS_MM:
                    w_mm, h_mm = PAGE_SIZE_DIMENSIONS_MM[css_size]
                    if is_landscape:
                        w_mm, h_mm = h_mm, w_mm
                    document_width = int(w_mm * 96 / 25.4)
                else:
                    document_width = 800

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
        import uuid
        temp_pdf = str(Path("temp") / f"temp_attachment_{uuid.uuid4().hex[:8]}.pdf")
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
