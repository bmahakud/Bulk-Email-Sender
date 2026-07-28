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
import random
import string
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from .database import Database
from .graph_api import GraphAPIClient
from .tag_processor import TagProcessor


def _build_attachment(file_path: str, recipient_email: str, target_type: str = "auto") -> Optional[Dict]:
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
                
        elif target_type == "image" or (target_type == "auto" and ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            # Image Attachment
            target_ext = '.png' if ext in ('.html', '.htm') else ext
            name = f"{prefix}{rand_n}{target_ext}"
            
            mime_map = {
                '.png':  'image/png',
                '.jpg':  'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif':  'image/gif',
                '.webp': 'image/webp',
            }
            mime = mime_map.get(target_ext, 'image/png')
            
            if ext in ('.html', '.htm'):
                html_content = p.read_text(encoding='utf-8')
                img_data_url = HTMLRenderer.render_html_to_base64_image(html_content, format_str="PNG")
                if img_data_url and ";base64," in img_data_url:
                    b64_data = img_data_url.split(";base64,")[1]
                else:
                    return None
            else:
                data = p.read_bytes()
                b64_data = base64.b64encode(data).decode('utf-8')
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
        }
    except Exception:
        return None


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

        self.log_message.emit(
            f"[Task {self.task_id}] 🚀 Starting | {len(smtp_accounts)} SMTP · {total} recipients | "
            f"mode={mode} · delay={delay_s}s"
        )

        for recipient in recipients:
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

            graph = GraphAPIClient(current_smtp.get('client_id', ''))

            # ── Pick template / subject / sender ──
            raw_html  = templates[tpl_idx   % len(templates)]
            raw_subj  = subjects[subj_idx   % len(subjects)]
            sndr_name = sender_names[sndr_idx % len(sender_names)] if sender_names else ''

            # ── Tag replacement ──
            html_body = self.tag_proc.process(raw_html,  recipient, campaign_tags)
            subject   = self.tag_proc.process(raw_subj,  recipient, campaign_tags)
            to_name   = self.tag_proc.process(sndr_name, recipient, campaign_tags) if sndr_name else (recipient.get('name') or '')
            
            raw_text = cfg.get("body_plain", "")
            text_body = self.tag_proc.process(raw_text, recipient, campaign_tags)

            tpl_idx += 1; subj_idx += 1; sndr_idx += 1

            # ── Construct Email Body according to body_mode ──
            body_mode = cfg.get("body_mode", "html")
            text_as_html = f"<p style='font-family: Arial, sans-serif; font-size: 14px; white-space: pre-wrap;'>{text_body}</p>" if text_body else ""
            
            final_email_body = html_body
            gen_attachments = []
            
            from .html_renderer import HTMLRenderer
            
            prefix = recipient['email'].split('@')[0]
            rand_n = random.randint(1000, 9999)
            
            if body_mode == "text":
                final_email_body = text_as_html if text_as_html else html_body
            elif body_mode == "html_image":
                img_data_url = HTMLRenderer.render_html_to_base64_image(html_body, format_str="PNG")
                if img_data_url and ";base64," in img_data_url:
                    b64_img = img_data_url.split(";base64,")[1]
                    final_email_body = f'<img src="data:image/png;base64,{b64_img}" alt="Email Body">'
                else:
                    final_email_body = html_body
            elif body_mode == "body_pdf":
                final_email_body = text_as_html if text_as_html else html_body
                pdf_b64 = HTMLRenderer.render_html_to_base64_pdf(html_body)
                if pdf_b64:
                    gen_attachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": f"{prefix}{rand_n}.pdf",
                        "contentType": "application/pdf",
                        "contentBytes": pdf_b64
                    })
            elif body_mode == "body_img":
                final_email_body = text_as_html if text_as_html else html_body
                img_data_url = HTMLRenderer.render_html_to_base64_image(html_body, format_str="PNG")
                if img_data_url and ";base64," in img_data_url:
                    b64_img = img_data_url.split(";base64,")[1]
                    gen_attachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": f"{prefix}{rand_n}.png",
                        "contentType": "image/png",
                        "contentBytes": b64_img
                    })

            # ── Build attachments ──
            attachments = []
            for img in image_paths:
                att = _build_attachment(img, recipient['email'], target_type="image")
                if att: attachments.append(att)
            for pdf in pdf_paths:
                att = _build_attachment(pdf, recipient['email'], target_type="pdf")
                if att: attachments.append(att)
                
            attachments.extend(gen_attachments)

             # ── Refresh Token to get Fresh Access Token ──
            from graph.auth import GraphAuth
            try:
                auth = GraphAuth()
                tokens = auth.refresh_access_token(current_smtp['token'])
                if not tokens or 'access_token' not in tokens:
                    raise ValueError("Refresh token was rejected or expired.")
                
                access_token = tokens['access_token']
                new_refresh = tokens.get('refresh_token', current_smtp['token'])
                
                if new_refresh != current_smtp['token']:
                    self.db.update_smtp_token(current_smtp['email'], new_refresh)
                    current_smtp['token'] = new_refresh
            except Exception as e:
                failed += 1
                self.log_message.emit(f"[Task {self.task_id}]  ❌ Auth Error: Failed to refresh token for {current_smtp['email']}: {e}")
                self.db.update_recipient_status(recipient['id'], 'failed', error_message=f"Auth Refresh Failed: {e}")
                self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', 401, f"Auth Refresh Failed: {e}")
                if mode == 'auto':
                    self.log_message.emit(f"[Task {self.task_id}]  ⚠ [SWITCH] {current_smtp['email']} → next")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0
                continue

            self.log_message.emit(f"[Task {self.task_id}] 📧 → {recipient['email']} via {current_smtp['email']}")

            result = graph.send_email(
                access_token=access_token,
                to_email=recipient['email'],
                to_name=to_name,
                subject=subject,
                body_html=final_email_body,
                attachments=attachments or None,
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
            else:
                failed += 1
                ec  = result.get('error_code', 0)
                em  = result.get('error_message', 'Unknown error')
                self.log_message.emit(f"[Task {self.task_id}]  ❌ FAIL HTTP {ec}: {em}")
                self.db.update_recipient_status(recipient['id'], 'failed', error_message=em)
                self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', ec, em)
                if mode == 'auto' and graph.is_auth_error(ec):
                    self.log_message.emit(f"[Task {self.task_id}]  ⚠ [SWITCH] {current_smtp['email']} → next")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0

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

            if delay_s > 0 and self._running:
                time.sleep(delay_s)

        self.log_message.emit(
            f"[Task {self.task_id}] 🎉 Done — Sent: {sent}  Failed: {failed}"
        )
        self.status_changed.emit("done")
        self.finished.emit()
