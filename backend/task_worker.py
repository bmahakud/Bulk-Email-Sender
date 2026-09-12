"""
Task Worker – background QThread for a single campaign task.
Supports:
  - SMTP rotation: auto (switch on auth error) | limit (switch after N emails)
  - Template, subject, sender-name rotation
  - All #TAG# replacement (via TagProcessor)
  - Base64 image / PDF attachments with personalised names
  - Pause / resume / stop
  - Auto-removal of sent recipients from the global pool
"""
import time
import base64
import hashlib
import random
import string
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from .database import Database
from .graph_api import GraphAPIClient
from .tag_processor import TagProcessor



# def _make_recipient_specific_image_bytes(
#     data: bytes,
#     recipient_email: str,
#     img_format: str,
#     max_kb: int = 100
# ) -> bytes:
#     """
#     Keep the uploaded image exactly as it is.
#     No background, footer, text, resizing, or format conversion.
#     """
#     return data




def _make_recipient_specific_image_bytes(
    data: bytes,
    recipient_email: str,
    img_format: str,
    max_kb: int = 100
) -> bytes:
    """
    Produces a unique Base64 string for every recipient while keeping the image
    visually identical. Strictly enforces size below 100KB.
    """
    import io
    import uuid
    import random
    import hashlib
    from PIL import Image, PngImagePlugin

    max_bytes = max_kb * 1024  # Strict 100 KB limit (102,400 bytes)

    try:
        in_buf = io.BytesIO(data)
        im = Image.open(in_buf)

        fmt = (img_format or im.format or "PNG").upper()
        if fmt == "JPG":
            fmt = "JPEG"

        # If it's an animated GIF, keep it as-is so frames aren't lost
        if getattr(im, "is_animated", False):
            return data

        # JPEG requires RGB mode (cannot save RGBA directly as JPEG)
        if fmt == "JPEG":
            if im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGB")
        else:
            im = im.copy()

        w, h = im.size
        px = im.load()

        # Seed random generator with recipient's email + entropy
        seed_str = f"{recipient_email}-{random.random()}"
        seed_val = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed_val)

        # Micro-pixel change: alter only 3 to 8 pixels by +/- 1 LSB (invisible to human eye)
        num_pixels = min(10, max(3, (w * h) // 10000))
        for _ in range(num_pixels):
            x = rng.randint(0, w - 1)
            y = rng.randint(0, h - 1)
            p = px[x, y]
            if isinstance(p, int):
                px[x, y] = p ^ 1
            else:
                ch = list(p)
                c_idx = rng.randint(0, min(2, len(ch) - 1))
                ch[c_idx] = max(0, min(255, ch[c_idx] + (1 if ch[c_idx] < 255 else -1)))
                px[x, y] = tuple(ch)

        out_buf = io.BytesIO()

        if fmt == "PNG":
            info = PngImagePlugin.PngInfo()
            info.add_text("X-UID", f"{recipient_email}-{uuid.uuid4().hex[:8]}")
            im.save(out_buf, format="PNG", pnginfo=info, optimize=True)
        elif fmt in ("JPEG", "WEBP"):
            quality = rng.randint(90, 95)
            save_kwargs = {"format": fmt, "quality": quality, "optimize": True}
            if fmt == "JPEG":
                save_kwargs["comment"] = f"{recipient_email}-{uuid.uuid4().hex[:8]}".encode()
            im.save(out_buf, **save_kwargs)
        else:
            im.save(out_buf, format=fmt)

        res = out_buf.getvalue()

        # If it fits within 100 KB, return immediately
        if len(res) <= max_bytes:
            return res

        # If slightly over 100 KB, reduce quality step-by-step to fit below 100 KB
        if fmt in ("JPEG", "WEBP"):
            for q in [85, 75, 65]:
                out_buf = io.BytesIO()
                im.save(out_buf, format=fmt, quality=q, optimize=True)
                if len(out_buf.getvalue()) <= max_bytes:
                    return out_buf.getvalue()
        elif fmt == "PNG":
            out_buf = io.BytesIO()
            im_quant = im.convert("P", palette=Image.ADAPTIVE, colors=256)
            im_quant.save(out_buf, format="PNG", optimize=True)
            if len(out_buf.getvalue()) <= max_bytes:
                return out_buf.getvalue()

        # Fallback: if original was already <= 100KB, return original
        if len(data) <= max_bytes:
            return data

        return res
    except Exception:
        # Failsafe: if anything goes wrong with PIL, return original bytes so sending never stops
        return data








def _build_attachment(file_path: str, recipient_email: str, target_type: str = "auto", img_format: str = None) -> Optional[Dict]:
    """
    Build a Microsoft Graph fileAttachment dict (base64-encoded).
    If target_type is 'pdf' and file is HTML, renders HTML to PDF attachment.
    If target_type is 'image' and file is HTML, renders HTML to Image attachment.
    """
    try:
        p = Path(file_path)
        if not p.exists():
            return None
        
        prefix = recipient_email.split('@')[0]
        rand_n = random.randint(1000, 9999)
        ext = p.suffix.lower()
        
        from .html_renderer import HTMLRenderer
        
        if target_type == "pdf" or (target_type == "auto" and ext == ".pdf"):
            # PDF Attachment
            name = f"{prefix}{rand_n}.pdf"
            mime = "application/pdf"
            if ext in ('.html', '.htm'):
                html_content = p.read_text(encoding='utf-8')
                b64_data = HTMLRenderer.render_html_to_base64_pdf(html_content)
                if not b64_data:
                    return None
            else:
                data = p.read_bytes()
                b64_data = base64.b64encode(data).decode('utf-8')
                
        elif target_type == "image" or (target_type == "auto" and ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff', '.tif')):
            # Image Attachment
            fmt_ext_map = {
                'JPG': '.jpg', 'JPEG': '.jpeg', 'PNG': '.png', 'WEBP': '.webp',
                'GIF': '.gif', 'BMP': '.bmp', 'TIFF': '.tiff',
            }
            # if ext in ('.html', '.htm'):
            #     target_ext = '.png'
            # else:
            #     target_ext = ext


            fmt_ext_map = {
                "PNG": ".png",
                "JPEG": ".jpeg",
                "JPG": ".jpg",
                "GIF": ".gif",
            }
            raw_sel = (img_format or "").strip().upper()
            if ext in ('.jpeg', '.jpg') and raw_sel in ('JPEG', 'JPG'):
                target_ext = ext
            elif raw_sel in fmt_ext_map:
                target_ext = fmt_ext_map[raw_sel]
            else:
                target_ext = ext if ext in ('.png', '.jpg', '.jpeg', '.gif') else ".jpeg"





            name = f"{prefix}{rand_n}{target_ext}"
            
            mime_map = {
                '.png':  'image/png',
                '.jpg':  'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif':  'image/gif',
                '.webp': 'image/webp',
                '.bmp':  'image/bmp',
                '.tiff': 'image/tiff',
                '.tif':  'image/tiff',
            }
            mime = mime_map.get(target_ext, 'image/png')
            
        #     if ext in ('.html', '.htm'):
        #         html_content = p.read_text(encoding='utf-8')
        #         img_data_url = HTMLRenderer.render_html_to_base64_image(html_content, format_str="PNG")
        #         if img_data_url and ";base64," in img_data_url:
        #             b64_data = img_data_url.split(";base64,")[1]
        #         else:
        #             return None
        #     else:
        #         data = p.read_bytes()
        #         b64_data = base64.b64encode(data).decode('utf-8')
        # else:


            if ext in ('.html', '.htm'):
                html_content = p.read_text(encoding='utf-8')
                img_data_url = HTMLRenderer.render_html_to_base64_image(html_content, format_str="PNG")
                if img_data_url and ";base64," in img_data_url:
                    raw_bytes = base64.b64decode(img_data_url.split(";base64,")[1])
                else:
                    return None
            else:
                raw_bytes = p.read_bytes()
                # raw_bytes = _make_recipient_specific_image_bytes(
                #     raw_bytes,
                #     recipient_email,
                #     ext
                # )


                raw_bytes = _make_recipient_specific_image_bytes(
                    raw_bytes,
                    recipient_email,
                    img_format or ext.lstrip(".")
)
            b64_data = base64.b64encode(raw_bytes).decode('utf-8')

            # Diagnostic only: fingerprint the Base64 generated for this image.
            b64_hash = hashlib.sha256(b64_data.encode('ascii')).hexdigest()
            diagnostic = (
                f"[Base64 image] "
                f"recipient={recipient_email} | "
                f"file={p.name} | "
                f"bytes={len(raw_bytes)} | "
                f"base64_length={len(b64_data)} | "
                f"base64_sha256={b64_hash}"
            )
            with open("base64_diagnostic.log", "a", encoding="utf-8") as f:
                f.write(diagnostic + "\n")






        else:
            # Fallback/Other Attachment Type
            mime_map = {
                '.html': 'text/html',
                '.txt': 'text/plain',
                '.csv': 'text/csv',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.zip': 'application/zip'
            }
            mime = mime_map.get(ext, 'application/octet-stream')
            name = f"{prefix}{rand_n}{ext}"
            data = p.read_bytes()
            b64_data = base64.b64encode(data).decode('utf-8')
            
        return {
            "@odata.type":  "#microsoft.graph.fileAttachment",
            "name":         name,
            "contentType":  mime,
            "contentBytes": b64_data,
            "isInline":     False,
        }
    except Exception:
        return None


# class TaskWorker(QThread):
#     """Background worker for a single campaign task."""





def _compress_image_bytes(data: bytes, ext: str = ".png", max_kb: int = 100, format_str: str = None) -> bytes:
    """
    Compress image bytes to be under max_kb KB, converting to format_str if given.
    Adds tiny per-call randomization (quality jitter + invisible pixel noise)
    so the same source image produces a different base64 string every call,
    while looking visually identical. Tries quality reduction, then resizing,
    then forced JPEG as last resort.
    """
    max_bytes = max_kb * 1024
    try:
        from PIL import Image
        import io
        import random as _random
        img = Image.open(io.BytesIO(data))
        fmt = (format_str or img.format or "PNG").upper()
        if fmt == "JPG":
            fmt = "JPEG"
        quality_formats = ("JPEG", "WEBP")
        if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        try:
            img = img.convert(img.mode)
            px = img.load()
            width, height = img.size
            num_noise_pixels = min(12, max(3, (width * height) // 5000))
            for _ in range(num_noise_pixels):
                x = _random.randint(0, width - 1)
                y = _random.randint(0, height - 1)
                pixel = px[x, y]
                if isinstance(pixel, int):
                    px[x, y] = pixel ^ 1
                else:
                    channels = list(pixel)
                    ci = _random.randint(0, len(channels) - 1)
                    channels[ci] = channels[ci] ^ 1
                    px[x, y] = tuple(channels)
        except Exception:
            pass
        base_quality = 95 if fmt in quality_formats else None
        if base_quality is not None:
            base_quality = _random.randint(max(1, base_quality - 4), base_quality)
        def _save(im, quality=None):
            buf = io.BytesIO()
            kwargs = {"format": fmt, "optimize": True}
            if fmt in quality_formats and quality is not None:
                kwargs["quality"] = quality
            im.save(buf, **kwargs)
            return buf
        buf = _save(img, quality=base_quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
        if fmt in quality_formats:
            for quality in [85, 70, 55, 40, 25, 15]:
                jittered_q = _random.randint(max(1, quality - 3), min(100, quality + 3))
                buf = _save(img, quality=jittered_q)
                if buf.tell() <= max_bytes:
                    return buf.getvalue()
        width, height = img.size
        current = img
        for _ in range(10):
            width = int(width * 0.85)
            height = int(height * 0.85)
            if width < 50 or height < 50:
                break
            current = img.resize((width, height), Image.LANCZOS)
            if fmt in quality_formats:
                buf = _save(current, quality=70)
            else:
                buf = _save(current)
            if buf.tell() <= max_bytes:
                return buf.getvalue()
        rgb_img = current.convert("RGB")
        for quality in [70, 55, 40, 25, 15, 10]:
            buf = io.BytesIO()
            rgb_img.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                return buf.getvalue()
        return buf.getvalue()
    except Exception:
        return data



class TaskWorker(QThread):
    """Background worker for a single campaign task."""




    log_message      = Signal(str)     # text log
    progress_updated = Signal(dict)    # {sent, failed, remaining, current_smtp}
    status_changed   = Signal(str)     # "running" | "paused" | "stopped" | "done"
    finished         = Signal()

    def __init__(self, task_id: int, config: Dict, db: Database):
        super().__init__()
        self.task_id  = task_id
        self.config   = config
        self.db       = db
        self.tag_proc = TagProcessor()

        self._running = True
        self._paused  = False

    # ── Controls ─────────────────────────────────────────────────────────────
    def pause(self):
        self._paused = True
        self.status_changed.emit("paused")
        self.log_message.emit(f"[Task {self.task_id}] ⏸ Paused")

    def resume(self):
        self._paused = False
        self.status_changed.emit("running")
        self.log_message.emit(f"[Task {self.task_id}] ▶ Resumed")

    def stop(self):
        self._running = False
        self._paused  = False
        self.status_changed.emit("stopped")
        self.log_message.emit(f"[Task {self.task_id}] ⏹ Stopped by user")

    # ── Main ─────────────────────────────────────────────────────────────────
    def run(self):
        self.status_changed.emit("running")
        cfg = self.config

        # ── Setup address pool for #ADDRESS# ──
        addr_list = [a.strip() for a in cfg.get('addresses', []) if a.strip()]
        self.tag_proc.set_address_pool(addr_list)

        # ── Pools ──
        templates    = cfg.get('templates', []) or ['<p>Hello #NAME#,<br>This is your message.</p>']
        subjects     = cfg.get('subjects',  []) or ['Hello #NAME#']
        sender_names = cfg.get('sender_names', [])
        campaign_tags = cfg.get('campaign_tags', {})

        image_paths = cfg.get('image_paths', [])
        pdf_paths   = cfg.get('pdf_paths',   [])

        delay_s        = float(cfg.get('delay', 1))
        mode           = cfg.get('smtp_mode', 'auto')   # 'auto' | 'limit'
        limit_per_smtp = int(cfg.get('limit_per_smtp', 5))
        auto_remove    = bool(cfg.get('auto_remove', True))

        # ── Ensure temp dir for HTMLRenderer ──
        Path("temp").mkdir(exist_ok=True)



        # ── Load data ──
        smtp_accounts = self.db.get_smtp_accounts(status='ready')
        recipients    = self.db.get_recipients(status='pending')

        if not smtp_accounts:
            self.log_message.emit(f"[Task {self.task_id}] ❌ No SMTP accounts – aborting"); self.finished.emit(); return
        if not recipients:
            self.log_message.emit(f"[Task {self.task_id}] ❌ No pending recipients – aborting"); self.finished.emit(); return

        total         = len(recipients)
        sent          = 0
        failed        = 0
        smtp_idx      = 0
        smtp_sent_cnt = 0
        tpl_idx = subj_idx = sndr_idx = 0

        # ── Pre-task silent sync of unsubscribed contacts from cloud ──
        try:
            token = self.db.get_setting("license_token", default="")
            lic_key = ""
            if token:
                from backend.license_validator import verify_token
                payload = verify_token(token)
                lic_key = payload.get("license_key", "")
            import requests
            url = "https://promailer-licensing.diracai.com/api/unsubscribed"
            params = {"lic": lic_key} if lic_key else {}
            resp = requests.get(url, params=params, timeout=3)
            if resp.status_code == 200:
                for item in resp.json().get("emails", []):
                    em = item.get("email", "").strip().lower()
                    if em:
                        self.db.add_unsubscribed(em)
        except Exception:
            pass

        self.log_message.emit(
            f"[Task {self.task_id}] 🚀 Starting | {len(smtp_accounts)} SMTP · {total} recipients | "
            f"mode={mode} · delay={delay_s}s"
        )

        recipients_queue = list(recipients)

        while recipients_queue:
            if not self._running:
                break
            while self._paused and self._running:
                time.sleep(0.3)
            if not self._running:
                break

            # Guard: if all SMTP exhausted
            active_smtps = [s for s in smtp_accounts if s.get('status', 'ready') == 'ready']
            if not active_smtps:
                self.log_message.emit(f"[Task {self.task_id}] ⚠ All SMTP exhausted"); break

            current_smtp = smtp_accounts[smtp_idx % len(smtp_accounts)]
            # Skip errored
            attempts = 0
            while current_smtp.get('status', 'ready') != 'ready' and attempts < len(smtp_accounts):
                smtp_idx += 1
                smtp_sent_cnt = 0
                current_smtp = smtp_accounts[smtp_idx % len(smtp_accounts)]
                attempts += 1
            if current_smtp.get('status', 'ready') != 'ready':
                self.log_message.emit(f"[Task {self.task_id}] ⚠ No ready SMTP left"); break

            # recipient = recipients_queue[0]
            # graph = GraphAPIClient(current_smtp.get('client_id', ''))

            # # ── Pick template / subject / sender ──
            # raw_html  = templates[tpl_idx   % len(templates)]
            # raw_subj  = subjects[subj_idx   % len(subjects)]
            # sndr_name = sender_names[sndr_idx % len(sender_names)] if sender_names else ''

            # # ── Tag replacement ──
            # html_body = self.tag_proc.process(raw_html,  recipient, campaign_tags, sender_name=sndr_name)
            # subject   = self.tag_proc.process(raw_subj,  recipient, campaign_tags, sender_name=sndr_name)
            # to_name   = self.tag_proc.process(sndr_name, recipient, campaign_tags, sender_name=sndr_name) if sndr_name else (recipient.get('name') or '')
            
            # raw_text = cfg.get("body_plain", "")
            # text_body = self.tag_proc.process(raw_text, recipient, campaign_tags, sender_name=sndr_name)



            recipient = recipients_queue[0]

            # ── Check if recipient is unsubscribed ──
            if self.db.is_unsubscribed(recipient.get('email', '')):
                self.log_message.emit(f"[Task {self.task_id}] ⏭️ Skipping unsubscribed recipient: {recipient['email']}")
                self.db.update_recipient_status(recipient['id'], 'skipped', error_message="Unsubscribed by recipient")
                recipients_queue.pop(0)
                continue

            graph = GraphAPIClient(current_smtp.get('client_id', ''))

            # ── Pick template / subject / sender ──
            raw_html  = templates[tpl_idx   % len(templates)] if templates else ""
            raw_subj  = subjects[subj_idx   % len(subjects)] if subjects else ""
            sndr_name = sender_names[sndr_idx % len(sender_names)] if sender_names else ''

            # ── Tag replacement ──
            sndr_email = current_smtp.get('email', '')
            html_body = self.tag_proc.process(raw_html,  recipient, campaign_tags, sender_name=sndr_name, sender_email=sndr_email)
            subject   = self.tag_proc.process(raw_subj,  recipient, campaign_tags, sender_name=sndr_name, sender_email=sndr_email)
            to_name   = self.tag_proc.process(sndr_name, recipient, campaign_tags, sender_name=sndr_name, sender_email=sndr_email) if sndr_name else (recipient.get('name') or '')
            
            raw_text = cfg.get("body_plain", "")
            text_body = self.tag_proc.process(raw_text, recipient, campaign_tags, sender_name=sndr_name, sender_email=sndr_email)



            
            
            
            
            # ── Construct Email Body and Attachments strictly isolated by body_mode ──
            body_mode = cfg.get("body_mode", "html")
            body_content_type = cfg.get("body_content_type", "html")
            if body_mode in ("text", "text_inline"):
                body_content_type = "text"
            elif body_mode == "html":
                body_content_type = "html"

            text_as_html = f"<p style='font-family: Arial, sans-serif; font-size: 14px; white-space: pre-wrap;'>{text_body}</p>" if text_body else ""
            
            final_email_body = ""
            attachments = []
            
            from .html_renderer import HTMLRenderer
            
            prefix = recipient['email'].split('@')[0]
            rand_n = random.randint(1000, 9999)

            # ── 1. BODY SELECTION PER MODE ──
            if body_mode == "text":
                final_email_body = text_as_html

            elif body_mode == "text_inline":
                final_email_body = text_as_html
                inline_images = []
                for idx, img in enumerate(image_paths):
                    try:
                        p = Path(img)
                        if not p.exists():
                            continue
                        ext = p.suffix.lower()
                        img_format = cfg.get("img_format")
                        raw_sel = (img_format or "").strip().upper()
                        fmt_ext_map = {
                            "PNG": ".png",
                            "JPEG": ".jpeg",
                            "JPG": ".jpg",
                            "GIF": ".gif",
                        }
                        if ext in ('.jpeg', '.jpg') and raw_sel in ('JPEG', 'JPG'):
                            target_ext = ext
                        elif raw_sel in fmt_ext_map:
                            target_ext = fmt_ext_map[raw_sel]
                        elif ext in ('.png', '.jpg', '.jpeg', '.gif'):
                            target_ext = ext
                        else:
                            target_ext = ".jpeg"

                        mime_map = {
                            ".png":  "image/png",
                            ".jpeg": "image/jpeg",
                            ".jpg":  "image/jpeg",
                            ".gif":  "image/gif",
                        }
                        mime = mime_map.get(target_ext, "image/jpeg")
                        content_id = f"body_img_{idx}_{rand_n}"

                        raw_bytes = p.read_bytes()
                        fmt_for_bytes = "PNG" if target_ext == ".png" else ("GIF" if target_ext == ".gif" else "JPEG")
                        raw_bytes = _make_recipient_specific_image_bytes(
                            raw_bytes,
                            recipient['email'],
                            fmt_for_bytes
                        )
                        img_b64 = base64.b64encode(raw_bytes).decode('utf-8')
                        b64_hash = hashlib.sha256(img_b64.encode('ascii')).hexdigest()
                        self.log_message.emit(
                            f"[Task {self.task_id}] Base64 inline image | "
                            f"recipient={recipient['email']} | "
                            f"bytes={len(raw_bytes)} | "
                            f"base64_length={len(img_b64)} | "
                            f"base64_sha256={b64_hash}"
                        )
                        img_html = f'<p align="center" style="margin: 15px 0;"><img src="cid:{content_id}" alt="" style="max-width:100%; height:auto; display:inline-block;"></p>'
                        if "#IMAGE#" in final_email_body:
                            final_email_body = final_email_body.replace("#IMAGE#", img_html, 1)
                        elif "#INLINE#" in final_email_body:
                            final_email_body = final_email_body.replace("#INLINE#", img_html, 1)
                        else:
                            inline_images.append(img_html)

                        attachments.append({
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": f"{p.stem}_{rand_n}{target_ext}",
                            "contentType": mime,
                            "contentBytes": img_b64,
                            "isInline": True,
                            "contentId": content_id,
                        })
                    except Exception as e:
                        self.log_message.emit(f"[Task {self.task_id}] ⚠️ Error preparing inline image: {e}")

                if inline_images:
                    joined_imgs = "\n" + "\n".join(inline_images) + "\n"
                    final_email_body += joined_imgs

            elif body_mode == "body_img_pdf":
                # Body+Img+PDF: Uploaded image is placed inside email body along with HTML, and PDF as attachment.
                # The HTML template is preserved exactly as it is.
                final_email_body = text_as_html if body_content_type == "text" else html_body

                inline_images = []
                for idx, img in enumerate(image_paths):
                    try:
                        p = Path(img)
                        if not p.exists():
                            continue
                        ext = p.suffix.lower()
                        img_format = cfg.get("img_format")
                        raw_sel = (img_format or "").strip().upper()
                        fmt_ext_map = {
                            "PNG": ".png",
                            "JPEG": ".jpeg",
                            "JPG": ".jpg",
                            "GIF": ".gif",
                        }
                        if ext in ('.jpeg', '.jpg') and raw_sel in ('JPEG', 'JPG'):
                            target_ext = ext
                        elif raw_sel in fmt_ext_map:
                            target_ext = fmt_ext_map[raw_sel]
                        elif ext in ('.png', '.jpg', '.jpeg', '.gif'):
                            target_ext = ext
                        else:
                            target_ext = ".jpeg"

                        mime_map = {
                            ".png":  "image/png",
                            ".jpeg": "image/jpeg",
                            ".jpg":  "image/jpeg",
                            ".gif":  "image/gif",
                        }
                        mime = mime_map.get(target_ext, "image/jpeg")
                        content_id = f"body_img_{idx}_{rand_n}"

                        raw_bytes = p.read_bytes()
                        fmt_for_bytes = "PNG" if target_ext == ".png" else ("GIF" if target_ext == ".gif" else "JPEG")
                        raw_bytes = _make_recipient_specific_image_bytes(
                            raw_bytes,
                            recipient['email'],
                            fmt_for_bytes
                        )
                        img_b64 = base64.b64encode(raw_bytes).decode('utf-8')
                        b64_hash = hashlib.sha256(img_b64.encode('ascii')).hexdigest()
                        self.log_message.emit(
                            f"[Task {self.task_id}] Base64 body image ({target_ext}) | "
                            f"recipient={recipient['email']} | "
                            f"bytes={len(raw_bytes)} | "
                            f"base64_length={len(img_b64)} | "
                            f"base64_sha256={b64_hash}"
                        )

                        img_html = f'<p align="center" style="margin: 15px 0;"><img src="cid:{content_id}" alt="" style="max-width:100%; height:auto; display:inline-block;"></p>'

                        if "#IMAGE#" in final_email_body:
                            final_email_body = final_email_body.replace("#IMAGE#", img_html, 1)
                        elif "#INLINE#" in final_email_body:
                            final_email_body = final_email_body.replace("#INLINE#", img_html, 1)
                        else:
                            inline_images.append(img_html)

                        attachments.append({
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name": f"{p.stem}_{rand_n}{target_ext}",
                            "contentType": mime,
                            "contentBytes": img_b64,
                            "isInline": True,
                            "contentId": content_id,
                        })
                    except Exception as e:
                        self.log_message.emit(f"[Task {self.task_id}] ⚠️ Error preparing body image: {e}")

                if inline_images:
                    joined_imgs = "\n" + "\n".join(inline_images) + "\n"
                    if "</body>" in final_email_body:
                        final_email_body = final_email_body.replace("</body>", f"{joined_imgs}</body>", 1)
                    elif "</html>" in final_email_body:
                        final_email_body = final_email_body.replace("</html>", f"{joined_imgs}</html>", 1)
                    else:
                        final_email_body += joined_imgs

            elif body_mode in ("inline_img", "inline_attach", "inline_pdf"):
                source_html = html_body
                if body_content_type == "text" and text_body:
                    source_html = (
                        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
                        f'<body style="margin:0; padding:25px; font-family:Arial,sans-serif; background:#ffffff; color:#222222; line-height:1.6; font-size:15px;">'
                        f'<div style="max-width:600px; margin:0 auto; white-space:pre-wrap;">{text_body}</div>'
                        f'</body></html>'
                    )
                if source_html:
                    try:
                        img_data_url = HTMLRenderer.render_html_to_base64_image(source_html, format_str="PNG")
                        if img_data_url and ";base64," in img_data_url:
                            raw_b64 = img_data_url.split(";base64,")[1]
                            raw_bytes = base64.b64decode(raw_b64)
                            raw_bytes = _make_recipient_specific_image_bytes(
                                raw_bytes,
                                recipient['email'],
                                "png"
                            )
                            img_b64 = base64.b64encode(raw_bytes).decode('utf-8')
                            content_id = f"body_img_{prefix}_{rand_n}"
                            b64_hash = hashlib.sha256(img_b64.encode('ascii')).hexdigest()
                            self.log_message.emit(
                                f"[Task {self.task_id}] Base64 image | "
                                f"recipient={recipient['email']} | "
                                f"bytes={len(raw_bytes)} | "
                                f"base64_length={len(img_b64)} | "
                                f"base64_sha256={b64_hash}"
                            )
                            attachments.append({
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": f"{prefix}{rand_n}.png",
                                "contentType": "image/png",
                                "contentBytes": img_b64,
                                "isInline": True,
                                "contentId": content_id,
                            })
                            final_email_body = (
                                f'<!DOCTYPE html><html><head><meta charset="utf-8">'
                                f'<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>'
                                f'<body style="margin:0; padding:10px; background-color:#ffffff; font-family:Arial,sans-serif; text-align:center;">'
                                f'<div style="max-width:650px; margin:0 auto; text-align:center;">'
                                f'<img src="cid:{content_id}" alt="" style="max-width:100%; height:auto; display:block; margin:0 auto;">'
                                f'</div></body></html>'
                            )
                    except Exception as e:
                        self.log_message.emit(f"[Task {self.task_id}] ⚠️ Could not render body image: {e}")
            else:
                # "html", "body_img", "body_pdf"
                if body_content_type == "text":
                    final_email_body = text_as_html
                else:
                    final_email_body = html_body

            # ── 2. ATTACHMENT SELECTION PER MODE (STRICT ISOLATION) ──
            img_format = cfg.get("img_format", "JPEG")

            # Image file attachments: ONLY for body_img (body_img_pdf embeds image directly inside the body)
            if body_mode == "body_img":
                for img in image_paths:
                    att = _build_attachment(img, recipient['email'], target_type="image", img_format=img_format)
                    if att:
                        attachments.append(att)

            # PDF attachments: ONLY for body_pdf, body_img_pdf, and inline_pdf
            if body_mode in ("body_pdf", "body_img_pdf", "inline_pdf"):
                if pdf_paths:
                    for pdf in pdf_paths:
                        att = _build_attachment(pdf, recipient['email'], target_type="pdf")
                        if att:
                            attachments.append(att)
                else:
                    source_for_pdf = html_body if body_content_type == "html" else text_as_html
                    if source_for_pdf:
                        try:
                            pdf_b64 = HTMLRenderer.render_html_to_base64_pdf(source_for_pdf)
                            if pdf_b64:
                                attachments.append({
                                    "@odata.type": "#microsoft.graph.fileAttachment",
                                    "name": f"{prefix}{rand_n}.pdf",
                                    "contentType": "application/pdf",
                                    "contentBytes": pdf_b64,
                                    "isInline": False
                                })
                        except Exception as e:
                            self.log_message.emit(f"[Task {self.task_id}] ⚠️ Could not generate PDF attachment: {e}")

            # ── 3. EMBEDDED LOGO / DATA:IMAGE CID CONVERSION ──
            if final_email_body and "data:image" in final_email_body:
                import re
                data_uri_regex = re.compile(r'<img([^>]+)src=["\']data:image/([a-zA-Z0-9+.-]+);base64,([A-Za-z0-9+/=]+)["\']([^>]*)>', re.IGNORECASE)
                embedded_seq = 0
                def _replace_data_uri_with_cid(m):
                    nonlocal embedded_seq
                    embedded_seq += 1
                    pre_attrs, itype, b64_str, post_attrs = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
                    if itype == "jpg":
                        itype = "jpeg"
                    cid_str = f"emb_img_{embedded_seq}_{rand_n}"
                    try:
                        raw_emb = base64.b64decode(b64_str)
                        raw_emb = _make_recipient_specific_image_bytes(
                            raw_emb,
                            recipient['email'],
                            itype
                        )
                        b64_str = base64.b64encode(raw_emb).decode('utf-8')
                    except Exception:
                        pass
                    attachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": f"{prefix}{rand_n}_emb{embedded_seq}.{itype}",
                        "contentType": f"image/{itype}",
                        "contentBytes": b64_str,
                        "isInline": True,
                        "contentId": cid_str,
                    })
                    return f'<img{pre_attrs}src="cid:{cid_str}"{post_attrs}>'

                final_email_body = data_uri_regex.sub(_replace_data_uri_with_cid, final_email_body)







             # ── Refresh Token to get Fresh Access Token ──
            from graph.auth import GraphAuth
            try:
                auth = GraphAuth(client_id=current_smtp['client_id'])
                tokens = auth.refresh_access_token(current_smtp['token'])
                if not tokens or 'access_token' not in tokens:
                    raise ValueError("Refresh token was rejected or expired.")
                
                access_token = tokens['access_token']
                new_refresh = tokens.get('refresh_token', current_smtp['token'])
                
                if new_refresh != current_smtp['token']:
                    self.db.update_smtp_token(current_smtp['email'], new_refresh)
                    current_smtp['token'] = new_refresh
            except Exception as e:
                self.log_message.emit(f"[Task {self.task_id}]  ❌ Auth Error: Failed to refresh token for {current_smtp['email']}: {e}")
                if mode == 'auto':
                    self.log_message.emit(f"[Task {self.task_id}]  ⚠ [SWITCH] {current_smtp['email']} → next")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0
                else:
                    failed += 1
                    self.db.update_recipient_status(recipient['id'], 'failed', error_message=f"Auth Refresh Failed: {e}")
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', 401, f"Auth Refresh Failed: {e}")
                    recipients_queue.pop(0)
                    tpl_idx += 1; subj_idx += 1; sndr_idx += 1
                continue

            self.log_message.emit(f"[Task {self.task_id}] 📧 → {recipient['email']} via {current_smtp['email']}")

            # result = graph.send_email(
            #     access_token=access_token,
            #     to_email=recipient['email'],
            #     to_name=to_name,
            #     subject=subject,
            #     body_html=final_email_body,
            #     attachments=attachments or None,
            # )


            # Retrieve active license key for client isolation
            lic_key = ""
            try:
                token = self.db.get_setting("license_token", default="")
                if token:
                    from backend.license_validator import verify_token
                    payload = verify_token(token)
                    lic_key = payload.get("license_key", "")
            except Exception:
                pass

            result = graph.send_email(
                access_token=access_token,
                to_email=recipient['email'],
                to_name=to_name,
                subject=subject,
                body_html=final_email_body,
                attachments=attachments or None,
                unsubscribe_email=current_smtp['email'],
                license_key=lic_key,
            )





            if result['success']:
                sent += 1
                smtp_sent_cnt += 1
                self.log_message.emit(f"[Task {self.task_id}]  ✅ OK → {recipient['email']}")
                if auto_remove:
                    self.db.delete_recipient(recipient['id'])
                else:
                    self.db.update_recipient_status(recipient['id'], 'sent', current_smtp['email'])
                self.db.increment_smtp_sent(current_smtp['email'])
                self.db.add_send_log(recipient['email'], current_smtp['email'], 'sent')
                
                # Advance inputs and remove recipient from front of queue
                recipients_queue.pop(0)
                tpl_idx += 1; subj_idx += 1; sndr_idx += 1
            else:
                ec  = result.get('error_code', 0)
                em  = result.get('error_message', 'Unknown error')
                
                # Is it an authentication error or rate/quota limit? (400, 401, 403, 429)
                if mode == 'auto' and (graph.is_auth_error(ec) or ec == 429):
                    self.log_message.emit(f"[Task {self.task_id}]  ❌ Sender Error on send via {current_smtp['email']} HTTP {ec}: {em} (Swapping sender...)")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0
                    time.sleep(0.5)
                    continue  # Retry same recipient with rotated SMTP
                else:
                    failed += 1
                    self.log_message.emit(f"[Task {self.task_id}]  ❌ FAIL HTTP {ec}: {em}")
                    self.db.update_recipient_status(recipient['id'], 'failed', error_message=em)
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', ec, em)
                    
                    # Discard recipient
                    recipients_queue.pop(0)
                    tpl_idx += 1; subj_idx += 1; sndr_idx += 1

            if mode == 'limit' and smtp_sent_cnt >= limit_per_smtp:
                self.log_message.emit(f"[Task {self.task_id}]  🔄 Limit {limit_per_smtp} reached → next SMTP")
                smtp_idx += 1
                smtp_sent_cnt = 0

            remaining = total - sent - failed
            self.progress_updated.emit({
                'sent': sent, 'failed': failed,
                'remaining': remaining,
                'current_smtp': current_smtp['email'],
            })

            if delay_s > 0 and self._running and recipients_queue:
                time.sleep(delay_s)

        self.log_message.emit(
            f"[Task {self.task_id}] 🎉 Done — Sent: {sent}  Failed: {failed}"
        )
        self.status_changed.emit("done")
        self.finished.emit()
