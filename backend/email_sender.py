"""
Email sending engine with SMTP rotation, template rotation, tag replacement, and attachments.
Supports:
  - body_mode: 'text' | 'html' | 'html_image' | 'body_pdf' | 'body_img'
  - HTML-file attachments rendered on-the-fly to PDF or Image via HTMLRenderer
  - Personalised attachment filenames: emailprefix + 4 random digits + extension
  - Full #TAG# / {{tag}} replacement for all campaign fields
  - SMTP rotation: 'auto' (switch on auth error) | 'limit' (switch after N emails)
  - Pause / Resume / Stop controls
"""
import time
import base64
import random
import itertools
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from .database import Database
from .graph_api import GraphAPIClient


class EmailSenderWorker(QThread):
    """Background worker for sending emails"""

    # Signals
    progress_updated = Signal(dict)   # {sent, failed, remaining, current_smtp}
    log_message = Signal(str)          # log lines
    finished = Signal()

    def __init__(self, config: Dict, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.graph_client = GraphAPIClient(config.get('client_id', ''))
        self.is_running = True
        self.is_paused = False

    # ── Controls ──────────────────────────────────────────────────────────────
    def pause(self):
        self.is_paused = True
        self.log_message.emit("⏸️ Campaign paused")

    def resume(self):
        self.is_paused = False
        self.log_message.emit("▶️ Campaign resumed")

    def stop(self):
        self.is_running = False
        self.log_message.emit("⏹️ Campaign stopped")

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _replace_tags(text: str, recipient: Dict, custom_tags: Dict) -> str:
        """Replace {{tag}} tokens in subject/body."""
        all_tags = {
            'name':      recipient.get('name', '') or recipient.get('email', '').split('@')[0],
            'email':     recipient.get('email', ''),
            'firstname': (recipient.get('name', '') or recipient.get('email', '')).split()[0],
        }
        all_tags.update(custom_tags)
        for key, val in all_tags.items():
            text = text.replace(f'{{{{{key}}}}}', str(val))
        return text

    @staticmethod
    def _build_attachment(file_path: str, recipient_email: str, target_type: str = "auto") -> Optional[Dict]:
        """
        Build a Microsoft Graph fileAttachment dict (base64-encoded).
        target_type: 'auto' | 'pdf' | 'image'
        If target_type is 'pdf' and file is .html, renders HTML → PDF.
        If target_type is 'image' and file is .html, renders HTML → PNG.
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
                name = f"{prefix}{rand_n}.pdf"
                mime = "application/pdf"
                if ext in ('.html', '.htm'):
                    b64_data = HTMLRenderer.render_html_to_base64_pdf(p.read_text(encoding='utf-8'))
                    if not b64_data:
                        return None
                else:
                    b64_data = base64.b64encode(p.read_bytes()).decode('utf-8')

            elif target_type == "image" or (target_type == "auto" and ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                target_ext = '.png' if ext in ('.html', '.htm') else ext
                name = f"{prefix}{rand_n}{target_ext}"
                mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif', '.webp': 'image/webp'}
                mime = mime_map.get(target_ext, 'image/png')
                if ext in ('.html', '.htm'):
                    img_url = HTMLRenderer.render_html_to_base64_image(p.read_text(encoding='utf-8'), format_str="PNG")
                    if img_url and ";base64," in img_url:
                        b64_data = img_url.split(";base64,")[1]
                    else:
                        return None
                else:
                    b64_data = base64.b64encode(p.read_bytes()).decode('utf-8')
            else:
                mime_map = {
                    '.html': 'text/html', '.txt': 'text/plain', '.csv': 'text/csv',
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.zip': 'application/zip'
                }
                mime = mime_map.get(ext, 'application/octet-stream')
                name = f"{prefix}{rand_n}{ext}"
                b64_data = base64.b64encode(p.read_bytes()).decode('utf-8')

            return {
                "@odata.type":  "#microsoft.graph.fileAttachment",
                "name":         name,
                "contentType":  mime,
                "contentBytes": b64_data,
            }
        except Exception:
            return None

    # ── Main loop ─────────────────────────────────────────────────────────────
    def run(self):
        try:
            self.log_message.emit("🚀 Starting email campaign…")

            cfg            = self.config
            delay_s        = float(cfg.get('delay', 1))
            mode           = cfg.get('mode', 'auto')         # 'auto' | 'limit'
            limit_per_smtp = int(cfg.get('limit_per_smtp', 5))
            auto_remove    = cfg.get('auto_remove', True)

            # Template / subject / sender pools
            templates    = cfg.get('templates', [])
            subjects     = cfg.get('subjects', [])
            sender_names = cfg.get('sender_names', [])
            custom_tags  = cfg.get('custom_tags', {})

            # Body mode configuration
            body_mode  = cfg.get('body_mode', 'html')
            body_plain = cfg.get('body_plain', '')

            # Address pool
            addr_pool = cfg.get('addresses', [])
            addr_iter = itertools.cycle(addr_pool) if addr_pool else None

            # Attachment file paths
            image_paths = cfg.get('image_paths', [])
            pdf_paths   = cfg.get('pdf_paths', [])

            # Ensure temp dir for HTMLRenderer
            Path("temp").mkdir(exist_ok=True)

            # Fallbacks
            if not templates:
                templates = ['<p>Hello {{name}},<br>This is your message.</p>']
            if not subjects:
                subjects  = ['Hello {{name}}']

            # Load data
            smtp_accounts = self.db.get_smtp_accounts(status='ready')
            recipients    = self.db.get_recipients(status='pending')

            if not smtp_accounts:
                self.log_message.emit("❌ No SMTP accounts available"); self.finished.emit(); return
            if not recipients:
                self.log_message.emit("❌ No pending recipients"); self.finished.emit(); return

            total         = len(recipients)
            sent_count    = 0
            failed_count  = 0
            smtp_index    = 0
            smtp_sent_cnt = 0
            tpl_idx = subj_idx = sndr_idx = 0

            self.log_message.emit(
                f"📊 {len(smtp_accounts)} SMTP · {total} recipients · "
                f"mode={mode} · delay={delay_s}s · body_mode={body_mode}"
            )

            for recipient in recipients:
                if not self.is_running:
                    break
                while self.is_paused and self.is_running:
                    time.sleep(0.3)
                if not self.is_running:
                    break

                current_smtp = smtp_accounts[smtp_index % len(smtp_accounts)]

                # Address cycling
                if addr_iter:
                    custom_tags['address'] = next(addr_iter)

                # Rotate pools
                html_template = templates[tpl_idx  % len(templates)]
                subject       = self._replace_tags(subjects[subj_idx % len(subjects)], recipient, custom_tags)
                sender_name   = sender_names[sndr_idx % len(sender_names)] if sender_names else ''
                tpl_idx += 1; subj_idx += 1; sndr_idx += 1

                to_name  = sender_name or (recipient.get('name') or '')
                html_body = self._replace_tags(html_template, recipient, custom_tags)
                text_body = self._replace_tags(body_plain, recipient, custom_tags) if body_plain else ''
                text_as_html = (
                    f"<p style='font-family:Arial,sans-serif;font-size:14px;white-space:pre-wrap;'>{text_body}</p>"
                ) if text_body else ''

                # ── Body mode dispatch ──
                from .html_renderer import HTMLRenderer
                prefix = recipient['email'].split('@')[0]
                rand_n = random.randint(1000, 9999)
                final_body = html_body
                gen_atts   = []

                if body_mode == 'text':
                    final_body = text_as_html if text_as_html else html_body

                elif body_mode == 'html_image':
                    img_url = HTMLRenderer.render_html_to_base64_image(html_body, format_str="PNG")
                    if img_url and ';base64,' in img_url:
                        b64 = img_url.split(';base64,')[1]
                        final_body = f'<img src="data:image/png;base64,{b64}" alt="Email Content" style="max-width:100%;">'
                    # else keep html_body

                elif body_mode == 'body_pdf':
                    final_body = text_as_html if text_as_html else html_body
                    pdf_b64 = HTMLRenderer.render_html_to_base64_pdf(html_body)
                    if pdf_b64:
                        gen_atts.append({
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name":         f"{prefix}{rand_n}.pdf",
                            "contentType":  "application/pdf",
                            "contentBytes": pdf_b64
                        })

                elif body_mode == 'body_img':
                    final_body = text_as_html if text_as_html else html_body
                    img_url = HTMLRenderer.render_html_to_base64_image(html_body, format_str="PNG")
                    if img_url and ';base64,' in img_url:
                        b64 = img_url.split(';base64,')[1]
                        gen_atts.append({
                            "@odata.type": "#microsoft.graph.fileAttachment",
                            "name":         f"{prefix}{rand_n}.png",
                            "contentType":  "image/png",
                            "contentBytes": b64
                        })

                # ── File attachments ──
                attachments = []
                for img in image_paths:
                    att = self._build_attachment(img, recipient['email'], target_type="image")
                    if att: attachments.append(att)
                for pdf in pdf_paths:
                    att = self._build_attachment(pdf, recipient['email'], target_type="pdf")
                    if att: attachments.append(att)
                attachments.extend(gen_atts)

                self.log_message.emit(f"📧 Sending to {recipient['email']} via {current_smtp['email']}")

                result = self.graph_client.send_email(
                    access_token=current_smtp['token'],
                    to_email=recipient['email'],
                    to_name=to_name,
                    subject=subject,
                    body_html=final_body,
                    attachments=attachments or None,
                )

                if result['success']:
                    sent_count    += 1
                    smtp_sent_cnt += 1
                    self.log_message.emit(f"  ✅ [OK] Sent to {recipient['email']}")
                    if auto_remove:
                        self.db.delete_recipient(recipient['id'])
                    else:
                        self.db.update_recipient_status(recipient['id'], 'sent', current_smtp['email'])
                    self.db.increment_smtp_sent(current_smtp['email'])
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'sent')
                else:
                    failed_count += 1
                    err_code = result.get('error_code', 0)
                    err_msg  = result.get('error_message', 'Unknown error')
                    self.log_message.emit(f"  ❌ [FAIL] {recipient['email']} HTTP {err_code}: {err_msg}")
                    self.db.update_recipient_status(recipient['id'], 'failed', error_message=err_msg)
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', err_code, err_msg)

                    if mode == 'auto' and self.graph_client.is_auth_error(err_code):
                        self.log_message.emit(f"  ⚠️ [SWITCH] {current_smtp['email']} bad → switching")
                        self.db.update_smtp_status(current_smtp['email'], 'error')
                        smtp_index    += 1
                        smtp_sent_cnt  = 0

                # Limit mode switch
                if mode == 'limit' and smtp_sent_cnt >= limit_per_smtp:
                    self.log_message.emit(f"  🔄 [SWITCH] Limit {limit_per_smtp} reached → next SMTP")
                    smtp_index    += 1
                    smtp_sent_cnt  = 0

                self.progress_updated.emit({
                    'sent':         sent_count,
                    'failed':       failed_count,
                    'remaining':    total - sent_count - failed_count,
                    'current_smtp': current_smtp['email'],
                })

                if delay_s > 0:
                    time.sleep(delay_s)

            self.log_message.emit(
                f"🎉 Campaign finished — Sent: {sent_count}  Failed: {failed_count}"
            )

        except Exception as e:
            self.log_message.emit(f"💥 Unexpected error: {e}")
        finally:
            self.finished.emit()
