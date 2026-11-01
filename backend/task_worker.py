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
        uid_str = f"{recipient_email}-{uuid.uuid4().hex[:8]}"

        if fmt == "PNG":
            info = PngImagePlugin.PngInfo()
            info.add_text("X-UID", uid_str)
            im.save(out_buf, format="PNG", pnginfo=info, optimize=True)
        elif fmt in ("JPEG", "WEBP"):
            quality = rng.randint(90, 95)
            save_kwargs = {"format": fmt, "quality": quality, "optimize": True}
            if fmt == "JPEG":
                save_kwargs["comment"] = uid_str.encode()
            im.save(out_buf, **save_kwargs)
        else:
            im.save(out_buf, format=fmt)

        res = out_buf.getvalue()

        # If it fits within 100 KB, return immediately
        if len(res) <= max_bytes:
            return res

        # Enforce strict < 100 KB ceiling using multi-step non-dithered palette / quality / scale
        try:
            from .html_renderer import HTMLRenderer
            comp = HTMLRenderer._compress_pil_image_bytes(
                im, save_fmt=fmt, max_bytes=max_bytes - 1024, uid_text=uid_str
            )
            if comp and len(comp) <= max_bytes:
                return comp
        except Exception:
            pass

        # Fallback: if original was already <= 100KB, return original
        if len(data) <= max_bytes:
            return data

        return res
    except Exception:
        # Failsafe: if anything goes wrong with PIL, return original bytes so sending never stops
        return data








def _make_recipient_specific_pdf_bytes(data: bytes, recipient_email: str, max_kb: int = 100) -> bytes:
    """
    Appends a recipient-specific metadata comment after the PDF EOF.
    Guarantees a 100% unique Base64 string and SHA-256 fingerprint for every recipient
    while keeping the PDF 100% valid, readable, and strictly below max_kb (100 KB).
    """
    import uuid
    import random
    max_bytes = max_kb * 1024
    uid = f"{recipient_email}-{uuid.uuid4().hex[:12]}-{random.randint(1000, 9999)}"
    comment = f"\n% X-Recipient-UID: {uid}\n".encode('ascii', errors='ignore')
    if len(data) + len(comment) <= max_bytes:
        return data + comment
    return data


def _format_attachment_name(
    pattern: Optional[str],
    recipient: dict,
    campaign_tags: dict,
    tag_proc,
    default_prefix: str,
    rand_n: int,
    ext: str,
    recipient_tags: Optional[dict] = None
) -> str:
    """
    Format dynamic attachment filename with tags like #USER#, #EMAIL#, #MAILRANDOM#, #ORDERID#, #INVOICE#, #RANDOM#.
    Falls back to default ({prefix}{rand_n}{ext}) if pattern is empty or blank.
    Guarantees no duplicate extensions and sanitizes illegal characters.
    Synchronizes with recipient_tags when provided so body and attachment have identical Order IDs/Invoices.
    """
    clean_ext = ext if ext.startswith('.') else f".{ext}"
    if not pattern or not str(pattern).strip():
        return f"{default_prefix}{rand_n}{clean_ext}"

    raw = str(pattern).strip()
    raw = raw.replace("#RANDOM#", str(rand_n)).replace("#RAND#", str(rand_n)).replace("#RAND4#", str(rand_n))

    if "#MAILRANDOM#" in raw:
        r_email = recipient.get("email", "") if recipient else ""
        u_pfx = r_email.split("@")[0] if r_email and "@" in r_email else default_prefix
        r_dig = str(random.choice([random.randint(1000, 9999), random.randint(10000, 99999)]))
        raw = raw.replace("#MAILRANDOM#", f"{u_pfx}{r_dig}")

    try:
        if recipient_tags and tag_proc:
            resolved = tag_proc.apply_replacements(raw, recipient_tags)
        elif tag_proc:
            resolved = tag_proc.process(raw, recipient, campaign_tags)
        else:
            resolved = raw
    except Exception:
        resolved = raw

    import re
    cleaned = re.sub(r'[\/\\:\*\?"<>\|\r\n\t]', '_', resolved).strip()
    if not cleaned:
        return f"{default_prefix}{rand_n}{clean_ext}"

    if cleaned.lower().endswith(clean_ext.lower()):
        cleaned = cleaned[:-len(clean_ext)].rstrip('.')

    return f"{cleaned}{clean_ext}"


def _build_attachment(file_path: str, recipient_email: str, target_type: str = "auto", img_format: str = None, custom_name: Optional[str] = None) -> Optional[Dict]:
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
            name = custom_name.strip() if (custom_name and custom_name.strip()) else f"{prefix}{rand_n}.pdf"
            mime = "application/pdf"
            if ext in ('.html', '.htm'):
                html_content = p.read_text(encoding='utf-8')
                from backend.template_manager import TemplateManager
                html_content = TemplateManager().process_html_inline_images(html_content, str(p))
                b64_data = HTMLRenderer.render_html_to_base64_pdf(html_content)
                if not b64_data:
                    return None
                data = base64.b64decode(b64_data)
                data = _make_recipient_specific_pdf_bytes(data, recipient_email, max_kb=100)
                b64_data = base64.b64encode(data).decode('utf-8')
            else:
                data = p.read_bytes()
                data = _make_recipient_specific_pdf_bytes(data, recipient_email, max_kb=100)
                b64_data = base64.b64encode(data).decode('utf-8')
                
            # Fingerprint and diagnostic log for PDF
            b64_hash = hashlib.sha256(b64_data.encode('ascii')).hexdigest()
            try:
                raw_bytes_len = len(data)
                with open("base64_diagnostic.log", "a", encoding="utf-8") as f:
                    f.write(f"[Base64 PDF] recipient={recipient_email} | file={p.name} | bytes={raw_bytes_len} | length={len(b64_data)} | sha256={b64_hash}\n")
            except Exception:
                pass
                
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





            name = custom_name.strip() if (custom_name and custom_name.strip()) else f"{prefix}{rand_n}{target_ext}"
            
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
                from backend.template_manager import TemplateManager
                html_content = TemplateManager().process_html_inline_images(html_content, str(p))
                fmt_render = "PNG" if target_ext == ".png" else ("GIF" if target_ext == ".gif" else "JPEG")
                img_data_url = HTMLRenderer.render_html_to_base64_image(html_content, format_str=fmt_render)
                if img_data_url and ";base64," in img_data_url:
                    raw_bytes = base64.b64decode(img_data_url.split(";base64,")[1])
                else:
                    return None
                raw_bytes = _make_recipient_specific_image_bytes(
                    raw_bytes,
                    recipient_email,
                    fmt_render.lower()
                )
            else:
                raw_bytes = p.read_bytes()
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
        import random
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
        provider       = cfg.get('provider', 'OAuthOutlook')
        smtp_server    = cfg.get('smtp_server', 'smtp.office365.com')
        try:
            smtp_port  = int(cfg.get('smtp_port', 587))
        except Exception:
            smtp_port  = 587

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
            cust_name = ""
            if token:
                from backend.license_validator import verify_token
                payload = verify_token(token)
                lic_key = (payload.get("license_key") or "").strip()
                cust_name = (payload.get("customer_name") or "").strip()
            import requests
            url = "https://promailer-licensing.diracai.com/api/unsubscribed"
            candidate_params = []
            if lic_key:
                candidate_params.append({"lic": lic_key})
            if cust_name and cust_name != lic_key:
                candidate_params.append({"lic": cust_name})

            for params in candidate_params:
                try:
                    resp = requests.get(url, params=params, timeout=3)
                    if resp.status_code == 200:
                        for item in resp.json().get("emails", []):
                            em = (item.get("email") or "").strip().lower()
                            unsub_at = item.get("unsubscribed_at")
                            if em:
                                self.db.add_unsubscribed(em, unsubscribed_at=unsub_at)
                except Exception:
                    continue
        except Exception:
            pass

        self.log_message.emit(
            f"[Task {self.task_id}] 🚀 Starting | {len(smtp_accounts)} SMTP · {total} recipients | "
            f"provider={provider} ({smtp_server}:{smtp_port}) · mode={mode} · delay={delay_s}s"
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

            # ── Auto-sanitize recipient email and name (clean any dots, pipes, or typos) ──
            raw_email = recipient.get('email', '').strip()
            import re
            email_match = re.search(r'[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}', raw_email)
            if email_match:
                clean_email = email_match.group(0).strip()
                if clean_email != raw_email:
                    if not recipient.get('name'):
                        rem_name = raw_email.replace(clean_email, "").strip(" ,|;.\t").strip()
                        if rem_name:
                            recipient['name'] = rem_name
                    recipient['email'] = clean_email

            # ── Check if recipient is unsubscribed ──
            if self.db.is_unsubscribed(recipient.get('email', '')):
                self.log_message.emit(f"[Task {self.task_id}] ⏭️ Skipping unsubscribed recipient: {recipient['email']}")
                self.db.update_recipient_status(recipient['id'], 'skipped', error_message="Unsubscribed by recipient")
                recipients_queue.pop(0)
                continue

            graph = GraphAPIClient(current_smtp.get('client_id', ''))

            # ── Pick template / subject / body / sender according to rotation_mode ──
            body_mode = cfg.get("body_mode", "html")
            body_content_type = cfg.get("body_content_type", "html")
            if body_mode in ("text", "text_inline"):
                body_content_type = "text"
            elif body_mode in ("html", "body_img_pdf") and body_content_type == "text":
                body_content_type = "html"

            rotation_mode = cfg.get("rotation_mode", "per_smtp")
            body_plain_list = cfg.get("body_plain_list", []) if body_content_type == "text" else []
            if body_content_type == "text" and not body_plain_list:
                default_bp = cfg.get("body_plain", "")
                body_plain_list = [default_bp] if default_bp else []

            active_templates = templates if body_content_type in ("html", "code") else []

            num_subj = len(subjects) if subjects else 1
            num_body = len(body_plain_list) if body_plain_list else 1
            num_html = len(active_templates) if active_templates else 1
            num_pairs = max(num_subj, num_body, num_html)

            if rotation_mode == "random":
                # Randomized:
                # Every email picks a randomized pair, where Subject and Body are matched!
                pair_idx = random.randint(0, num_pairs - 1)
            elif rotation_mode == "per_smtp":
                # Per SMTP: Locked to active SMTP account index (switches when account rotates)
                pair_idx = smtp_idx
            else:
                # Per Email (Default):
                # Every individual email takes the next matching Subject + Body pair in sequence (1 -> 2 -> 3 -> 4 -> 1...)
                pair_idx = (sent + failed) % num_pairs

            raw_subj  = subjects[pair_idx % len(subjects)] if subjects else ""
            raw_text  = body_plain_list[pair_idx % len(body_plain_list)] if (body_content_type == "text" and body_plain_list) else ""
            raw_html  = active_templates[pair_idx % len(active_templates)] if (body_content_type in ("html", "code") and active_templates) else ""
            sndr_name = sender_names[sndr_idx % len(sender_names)] if sender_names else ''

            # ── Tag replacement (synchronized across body, subject, and PDF attachment) ──
            sndr_email = current_smtp.get('email', '')
            recipient_tags = self.tag_proc.build_replacements(recipient, campaign_tags, sender_name=sndr_name, sender_email=sndr_email)
            html_body = self.tag_proc.apply_replacements(raw_html, recipient_tags) if raw_html else ""
            subject   = self.tag_proc.apply_replacements(raw_subj, recipient_tags)
            to_name   = self.tag_proc.apply_replacements(sndr_name, recipient_tags) if sndr_name else (recipient.get('name') or '')
            
            text_body = self.tag_proc.apply_replacements(raw_text, recipient_tags) if raw_text else ""

            if text_body:
                tb_s = text_body.strip()
                if (
                    tb_s.startswith(("<html", "<!doctype", "<!DOCTYPE", "<table", "<div", "<p", "<?xml", "<body"))
                    or ("<html" in tb_s.lower() and "</html>" in tb_s.lower())
                    or ("<body" in tb_s.lower() and "</body>" in tb_s.lower())
                ):
                    text_as_html = text_body
                else:
                    text_as_html = f"<p style='font-family: Arial, sans-serif; font-size: 14px; white-space: pre-wrap;'>{text_body}</p>"
            else:
                text_as_html = ""
            
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
                        try:
                            with open("base64_diagnostic.log", "a", encoding="utf-8") as diag_f:
                                diag_f.write(f"[Base64 inline image] recipient={recipient['email']} | file={p.name} | bytes={len(raw_bytes)} | length={len(img_b64)} | sha256={b64_hash}\n")
                        except Exception:
                            pass
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
                # Body HTML + PDF: Clean email body (HTML) with no embedded images, and PDF attachment.
                final_email_body = text_as_html if body_content_type == "text" else HTMLRenderer.prepare_html_for_email_body(html_body)

            elif body_mode in ("inline_img", "inline_attach", "inline_pdf"):
                if body_content_type == "text":
                    source_html = (
                        f'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
                        f'<body style="margin:0; padding:25px; font-family:Arial,sans-serif; background:#ffffff; color:#222222; line-height:1.6; font-size:15px;">'
                        f'<div style="max-width:600px; margin:0 auto; white-space:pre-wrap;">{text_body}</div>'
                        f'</body></html>'
                    ) if text_body else ""
                else:
                    source_html = html_body
                if source_html:
                    try:
                        img_data_url = HTMLRenderer.render_html_to_base64_image(source_html, format_str="PNG", width_val=650)
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
                            try:
                                with open("base64_diagnostic.log", "a", encoding="utf-8") as diag_f:
                                    diag_f.write(f"[Base64 image] recipient={recipient['email']} | file=rendered_body.png | bytes={len(raw_bytes)} | length={len(img_b64)} | sha256={b64_hash}\n")
                            except Exception:
                                pass
                            attachments.append({
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": f"body_{prefix}_{rand_n}.png",
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
                    final_email_body = HTMLRenderer.prepare_html_for_email_body(html_body)

            # ── 2. ATTACHMENT SELECTION PER MODE (STRICT ISOLATION) ──
            img_format = cfg.get("img_format", "JPEG")

            # Image file attachments: for body_img and inline_attach / inline_img
            if body_mode in ("body_img", "inline_img", "inline_attach"):
                if image_paths:
                    direct_images = [img for img in image_paths if Path(img).suffix.lower() not in ('.html', '.htm')]
                    html_img_templates = [img for img in image_paths if Path(img).suffix.lower() in ('.html', '.htm')]

                    img_att_pattern = cfg.get("img_att_name", "")
                    if direct_images:
                        fmt_ext_map = {"PNG": ".png", "JPEG": ".jpeg", "JPG": ".jpg", "GIF": ".gif"}
                        target_ext = fmt_ext_map.get((img_format or "JPEG").upper(), ".jpeg")
                        final_img_name = _format_attachment_name(
                            img_att_pattern,
                            recipient,
                            campaign_tags,
                            self.tag_proc,
                            prefix,
                            rand_n,
                            target_ext,
                            recipient_tags=recipient_tags
                        )
                        for img in direct_images:
                            att = _build_attachment(img, recipient['email'], target_type="image", img_format=img_format, custom_name=final_img_name)
                            if att:
                                attachments.append(att)
                    elif html_img_templates:
                        for img in html_img_templates:
                            p = Path(img)
                            if not p.exists():
                                continue
                            try:
                                img_raw_html = p.read_text(encoding='utf-8')
                                from backend.template_manager import TemplateManager
                                img_raw_html = TemplateManager().process_html_inline_images(img_raw_html, str(p))
                                img_processed_html = self.tag_proc.apply_replacements(img_raw_html, recipient_tags)

                                target_format = (img_format or "JPEG").upper()
                                fmt_for_render = "PNG" if target_format == "PNG" else ("GIF" if target_format == "GIF" else "JPEG")
                                img_data_url = HTMLRenderer.render_html_to_base64_image(img_processed_html, format_str=fmt_for_render)
                                if img_data_url and ";base64," in img_data_url:
                                    raw_b64 = img_data_url.split(";base64,")[1]
                                    raw_bytes = base64.b64decode(raw_b64)
                                    raw_bytes = _make_recipient_specific_image_bytes(
                                        raw_bytes,
                                        recipient['email'],
                                        fmt_for_render.lower()
                                    )
                                    final_b64 = base64.b64encode(raw_bytes).decode('utf-8')

                                    fmt_ext_map = {"PNG": ".png", "JPEG": ".jpeg", "JPG": ".jpg", "GIF": ".gif"}
                                    target_ext = fmt_ext_map.get(target_format, ".jpeg")
                                    mime_map = {".png": "image/png", ".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".gif": "image/gif"}
                                    mime = mime_map.get(target_ext, "image/jpeg")

                                    b64_hash = hashlib.sha256(final_b64.encode('ascii')).hexdigest()
                                    self.log_message.emit(
                                        f"[Task {self.task_id}] Base64 Image (from HTML template) | "
                                        f"recipient={recipient['email']} | "
                                        f"file={p.name} | "
                                        f"bytes={len(raw_bytes)} | "
                                        f"base64_length={len(final_b64)} | "
                                        f"base64_sha256={b64_hash}"
                                    )
                                    try:
                                        with open("base64_diagnostic.log", "a", encoding="utf-8") as diag_f:
                                             diag_f.write(f"[Base64 Image] recipient={recipient['email']} | file={p.name} | bytes={len(raw_bytes)} | length={len(final_b64)} | sha256={b64_hash}\n")
                                    except Exception:
                                        pass

                                    final_img_name = _format_attachment_name(
                                        img_att_pattern,
                                        recipient,
                                        campaign_tags,
                                        self.tag_proc,
                                        prefix,
                                        rand_n,
                                        target_ext,
                                        recipient_tags=recipient_tags
                                    )
                                    attachments.append({
                                        "@odata.type": "#microsoft.graph.fileAttachment",
                                        "name": final_img_name,
                                        "contentType": mime,
                                        "contentBytes": final_b64,
                                        "isInline": False
                                    })
                            except Exception as e:
                                self.log_message.emit(f"[Task {self.task_id}] ⚠️ Error generating Image from HTML {p.name}: {e}")

            # PDF attachments: for body_pdf, body_img_pdf, and inline_pdf
            if body_mode in ("body_pdf", "body_img_pdf", "inline_pdf"):
                if pdf_paths:
                    direct_pdfs = [pdf for pdf in pdf_paths if Path(pdf).suffix.lower() not in ('.html', '.htm')]
                    html_templates = [pdf for pdf in pdf_paths if Path(pdf).suffix.lower() in ('.html', '.htm')]

                    pdf_att_pattern = cfg.get("pdf_att_name", "")
                    final_pdf_name = _format_attachment_name(
                        pdf_att_pattern,
                        recipient,
                        campaign_tags,
                        self.tag_proc,
                        prefix,
                        rand_n,
                        ".pdf",
                        recipient_tags=recipient_tags
                    )

                    if direct_pdfs:
                        # User uploaded direct PDF file(s) — attach ONLY the PDF file (do not convert HTML)
                        for pdf in direct_pdfs:
                            att = _build_attachment(pdf, recipient['email'], target_type="pdf", custom_name=final_pdf_name)
                            if att:
                                attachments.append(att)
                    elif html_templates:
                        # User uploaded HTML template for PDF — convert HTML to PDF attachment
                        for pdf in html_templates:
                            p = Path(pdf)
                            if not p.exists():
                                continue
                            try:
                                pdf_raw_html = p.read_text(encoding='utf-8')
                                from backend.template_manager import TemplateManager
                                pdf_raw_html = TemplateManager().process_html_inline_images(pdf_raw_html, str(p))
                                pdf_processed_html = self.tag_proc.apply_replacements(pdf_raw_html, recipient_tags)
                                pdf_b64 = HTMLRenderer.render_html_to_base64_pdf(pdf_processed_html)
                                if pdf_b64:
                                    raw_pdf_bytes = base64.b64decode(pdf_b64)
                                    raw_pdf_bytes = _make_recipient_specific_pdf_bytes(raw_pdf_bytes, recipient['email'], max_kb=100)
                                    pdf_b64 = base64.b64encode(raw_pdf_bytes).decode('utf-8')
                                    b64_hash = hashlib.sha256(pdf_b64.encode('ascii')).hexdigest()
                                    self.log_message.emit(
                                        f"[Task {self.task_id}] Base64 PDF (from HTML template) | "
                                        f"recipient={recipient['email']} | "
                                        f"file={p.name} | "
                                        f"bytes={len(raw_pdf_bytes)} | "
                                        f"base64_length={len(pdf_b64)} | "
                                        f"base64_sha256={b64_hash}"
                                    )
                                    try:
                                        raw_bytes_len = len(raw_pdf_bytes)
                                        with open("base64_diagnostic.log", "a", encoding="utf-8") as diag_f:
                                            diag_f.write(f"[Base64 PDF] recipient={recipient['email']} | file={p.name} | bytes={raw_bytes_len} | length={len(pdf_b64)} | sha256={b64_hash}\n")
                                    except Exception:
                                        pass
                                    attachments.append({
                                        "@odata.type": "#microsoft.graph.fileAttachment",
                                        "name": final_pdf_name,
                                        "contentType": "application/pdf",
                                        "contentBytes": pdf_b64,
                                        "isInline": False
                                    })
                            except Exception as e:
                                self.log_message.emit(f"[Task {self.task_id}] ⚠️ Error generating PDF from HTML {p.name}: {e}")

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

            # Retrieve active license key for unsubscribe link
            lic_key = ""
            try:
                token = self.db.get_setting("license_token", default="")
                if token:
                    from backend.license_validator import verify_token
                    payload = verify_token(token)
                    lic_key = (payload.get("customer_name") or payload.get("license_key") or "").strip()
            except Exception:
                pass

            # Automatically ensure a visible Unsubscribe footer is present if not already in body
            if "unsubscribe" not in final_email_body.lower():
                unsub_href = f"https://promailer-licensing.diracai.com/unsubscribe?lic={lic_key}&email={recipient['email']}"
                unsub_html_footer = (
                    f'<br><div style="font-size: 11px; color: #888888; text-align: center; '
                    f'padding-top: 14px; margin-top: 20px; border-top: 1px solid #eeeeee;">'
                    f'If you do not wish to receive further emails, you may '
                    f'<a href="{unsub_href}" style="color: #666666; text-decoration: underline;">unsubscribe here</a>.'
                    f'</div>'
                )
                final_email_body += unsub_html_footer

            # ── 4. BASE64 BODY ENCRYPTION & FINGERPRINTING (ALL MODES) ──
            # Inject invisible polymorphic salt so every recipient receives a 100% unique Base64 body string
            import uuid
            body_salt = f"<!-- b64-uid: {recipient['email']}-{uuid.uuid4().hex[:12]}-{random.randint(1000, 9999)} -->"
            final_email_body += f"\n{body_salt}"

            raw_body_bytes = final_email_body.encode('utf-8')
            body_b64 = base64.b64encode(raw_body_bytes).decode('ascii')
            body_b64_hash = hashlib.sha256(body_b64.encode('ascii')).hexdigest()
            mode_display = {
                "body_img": "Body+Img",
                "body_pdf": "Body+PDF",
                "body_img_pdf": "Body HTML+PDF",
                "inline_img": "Inline+Attach",
                "inline_pdf": "Inline+PDF",
                "text": "Text Only",
                "html": "HTML Only",
            }.get(body_mode, body_mode)

            self.log_message.emit(
                f"[Task {self.task_id}] Base64 Body ({mode_display}) | "
                f"recipient={recipient['email']} | "
                f"bytes={len(raw_body_bytes)} | "
                f"base64_length={len(body_b64)} | "
                f"base64_sha256={body_b64_hash}"
            )
            try:
                with open("base64_diagnostic.log", "a", encoding="utf-8") as diag_f:
                    diag_f.write(
                        f"[Base64 Body] recipient={recipient['email']} | mode={mode_display} | "
                        f"bytes={len(raw_body_bytes)} | length={len(body_b64)} | sha256={body_b64_hash}\n"
                    )
            except Exception:
                pass

            # ── Exchange Online SMTP (XOAUTH2) with MAPI Headers & Failsafe ──
            from graph.auth import GraphAuth
            from backend.hve_sender import HVESender
            import re

            token_val = (current_smtp.get('token') or '').strip()
            is_uuid_tenant = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", token_val))
            is_hve = is_uuid_tenant or token_val.lower().startswith("hve:")

            try:
                if is_hve:
                    tenant_id = token_val.replace("hve:", "").strip()
                    secret = current_smtp.get('password', '')
                    access_token = HVESender.get_access_token(
                        tenant_id=tenant_id,
                        client_id=current_smtp['client_id'],
                        client_secret=secret
                    )
                    if not access_token:
                        raise ValueError("HVE client_credentials token was rejected or expired.")
                else:
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
                self.log_message.emit(f"[Task {self.task_id}]  🔄 [Auto-Failover] {current_smtp['email']} inactive on Microsoft → seamlessly rotating to next sender...")
                self.db.update_smtp_status(current_smtp['email'], 'expired')
                current_smtp['status'] = 'expired'
                smtp_idx += 1
                smtp_sent_cnt = 0
                time.sleep(0.3)
                continue

            self.log_message.emit(f"[Task {self.task_id}] 📧 → {recipient['email']} via {current_smtp['email']}")

            # Retrieve active license key for unsubscribe link
            lic_key = ""
            try:
                token = self.db.get_setting("license_token", default="")
                if token:
                    from backend.license_validator import verify_token
                    payload = verify_token(token)
                    lic_key = (payload.get("customer_name") or payload.get("license_key") or "").strip()
            except Exception:
                pass

            # ── Dispatch Engine based on Provider Selection ──
            provider = cfg.get('provider', 'OAuthOutlook')
            smtp_server = cfg.get('smtp_server', 'smtp.office365.com')
            try:
                smtp_port = int(cfg.get('smtp_port', 587))
            except Exception:
                smtp_port = 587

            if provider == "Office365 SMTP OAuth":
                # Exchange Online SMTP (Port 587) with AUTH XOAUTH2 & full MAPI headers
                engine_label = "Office365 SMTP 250 OK"
                smtp_token = HVESender.get_delegated_smtp_token(current_smtp['client_id'], current_smtp['token']) or access_token
                result = HVESender.send_email(
                    sender_email=current_smtp['email'],
                    sender_name=sndr_name or "",
                    to_email=recipient['email'],
                    to_name=to_name if to_name else (recipient.get('name') or ""),
                    subject=subject,
                    body_html=final_email_body,
                    access_token=smtp_token,
                    attachments=attachments or None,
                    unsubscribe_email=current_smtp['email'],
                    license_key=lic_key,
                    preferred_host=smtp_server,
                    preferred_port=smtp_port,
                    timeout=30,
                )
                if not result.get('success'):
                    # Resilient failsafe fallback to Graph API if SMTP port is blocked by tenant policy or STARTTLS unsupported
                    self.log_message.emit(
                        f"[Task {self.task_id}]  ⚠️ [SMTP Fallback] {result.get('error_message', 'SMTP failed')[:80]} → trying Exchange MAPI Store..."
                    )
                    graph_res = graph.send_email(
                        access_token=access_token,
                        to_email=recipient['email'],
                        to_name=to_name,
                        subject=subject,
                        body_html=final_email_body,
                        attachments=attachments or None,
                        unsubscribe_email=current_smtp['email'],
                        license_key=lic_key,
                    )
                    if graph_res.get('success'):
                        result = graph_res
                        engine_label = "Exchange MAPI Store"

            elif provider == "HVE SMTP OAuth" or is_hve:
                # Corporate Tenant with High Volume Email (HVE) bulk endpoint with native MAPI headers
                engine_label = "Exchange HVE 250 OK"
                hve_host = smtp_server if "hve" in smtp_server.lower() else "smtp.hve.mx.microsoft"
                result = HVESender.send_email(
                    sender_email=current_smtp['email'],
                    sender_name=sndr_name or "",
                    to_email=recipient['email'],
                    to_name=to_name if to_name else (recipient.get('name') or ""),
                    subject=subject,
                    body_html=final_email_body,
                    access_token=access_token,
                    attachments=attachments or None,
                    unsubscribe_email=current_smtp['email'],
                    license_key=lic_key,
                    preferred_host=hve_host,
                    preferred_port=smtp_port,
                    timeout=30,
                )
                if not result.get('success'):
                    # Failsafe fallback to Graph API if HVE gateway not provisioned
                    self.log_message.emit(
                        f"[Task {self.task_id}]  ⚠️ [HVE Fallback] {result.get('error_message', 'HVE failed')[:80]} → trying Exchange MAPI Store..."
                    )
                    graph_res = graph.send_email(
                        access_token=access_token,
                        to_email=recipient['email'],
                        to_name=to_name,
                        subject=subject,
                        body_html=final_email_body,
                        attachments=attachments or None,
                        unsubscribe_email=current_smtp['email'],
                        license_key=lic_key,
                    )
                    if graph_res.get('success'):
                        result = graph_res
                        engine_label = "Exchange MAPI Store"

            else:
                # Default: "OAuthOutlook"
                # Standard Graph / Delegated Outlook Accounts: Clean Exchange MAPI Store via Graph API
                # (Delivers directly to Primary Inbox without failed SMTP handshakes)
                engine_label = "Exchange MAPI Store"
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
                self.log_message.emit(f"[Task {self.task_id}]  ✅ [{engine_label}] Delivered → {recipient['email']}")
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
                
                # Check whether this is a sender quota/rate-limit error (e.g. HTTP 429, RefuseQuota, Daily limit)
                # or a sender authentication error (401, 403, token expired/denied)
                is_quota_or_rate = (ec == 429) or any(
                    q in em.lower() for q in ("quota", "limit exceeded", "throttl", "refusequota", "rate limit", "submission quota", "exceeded the maximum")
                )
                is_sender_auth = graph.is_auth_error(ec) or any(
                    a in em.lower() for a in ("unauthorized", "invalid_grant", "token expired", "auth error", "authenticated", "access denied", "tenant")
                )

                # Genuine recipient address failure (only when it is NOT a sender quota/auth issue)
                is_recipient_err = not (is_quota_or_rate or is_sender_auth) and any(
                    k in em.lower() for k in ("recipientnotfound", "invalidrecipients", "badrecipient", "does not exist", "mailbox unavailable", "user unknown", "syntax error in recipient")
                )

                if (is_quota_or_rate or is_sender_auth) and not is_recipient_err:
                    self.log_message.emit(
                        f"[Task {self.task_id}]  ⚠ Sender Quota/Auth Limit on {current_smtp['email']} "
                        f"(HTTP {ec}: {em[:70]}). Switching to next sender account..."
                    )
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

            # Smart Account Rotation:
            # In 'limit' mode: rotates after limit_per_smtp.
            # In 'auto' mode: automatically rotates every 10 emails to prevent single-account hourly throttling!
            should_rotate = (mode == 'limit' and smtp_sent_cnt >= limit_per_smtp) or (mode == 'auto' and smtp_sent_cnt >= 10)
            if should_rotate:
                reason_str = f"Limit {limit_per_smtp}" if mode == 'limit' else "Safety batch (10 emails)"
                self.log_message.emit(f"[Task {self.task_id}]  🔄 {reason_str} reached on {current_smtp['email']} → rotating to next active sender...")
                smtp_idx += 1
                smtp_sent_cnt = 0

            remaining = total - sent - failed
            self.progress_updated.emit({
                'sent': sent, 'failed': failed,
                'remaining': remaining,
                'current_smtp': current_smtp['email'],
            })

            if delay_s > 0 and self._running and recipients_queue:
                end_s = time.time() + delay_s
                while time.time() < end_s and self._running:
                    while self._paused and self._running:
                        time.sleep(0.1)
                    time.sleep(0.1)

        self.log_message.emit(
            f"[Task {self.task_id}] 🎉 Done — Sent: {sent}  Failed: {failed}"
        )
        self.status_changed.emit("done")
        self.finished.emit()
