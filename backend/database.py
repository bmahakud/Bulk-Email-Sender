"""
Database manager for storing SMTP accounts and recipients
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = "data/mailer.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # SMTP Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smtp_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                token TEXT,
                client_id TEXT NOT NULL,
                status TEXT DEFAULT 'ready',
                emails_sent INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Recipients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                name TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP,
                smtp_email TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Send logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS send_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_email TEXT NOT NULL,
                smtp_email TEXT NOT NULL,
                status TEXT NOT NULL,
                error_code INTEGER,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

                # Unsubscribed recipients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unsubscribed_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                unsubscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tracks processed inbox List-Unsubscribe mailto messages so removed contacts do not re-appear
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_unsub_messages (
                msg_id TEXT PRIMARY KEY,
                sender_email TEXT,
                unsub_email TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tracks user-removed suppression entries so background cloud/inbox syncs do not resurrect old records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS removed_unsubscribes (
                email TEXT PRIMARY KEY,
                suppressed_unsub_at TEXT DEFAULT '',
                removed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


        

        # Settings table (for persistent configs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                content TEXT
            )
        """)

        # Subject Lines table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT UNIQUE
            )
        """)

        # Sender Names table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sender_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        
        # Auto-cleanup corrupted recipient entries and restore SMTP accounts to ready
        cursor.execute("DELETE FROM recipients WHERE email LIKE '% %'")
        cursor.execute("UPDATE smtp_accounts SET status='ready' WHERE status='error'")

        conn.commit()
        conn.close()

    
    # SMTP Accounts Methods
    def add_smtp_account(self, email: str, password: str, token: str, client_id: str) -> int:
        """Add SMTP account"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO smtp_accounts (email, password, token, client_id)
                VALUES (?, ?, ?, ?)
            """, (email, password, token, client_id))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Update existing and reset status to ready
            cursor.execute("""
                UPDATE smtp_accounts 
                SET password=?, token=?, client_id=?, status='ready'
                WHERE email=?
            """, (password, token, client_id, email))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_smtp_accounts_bulk(self, accounts: List[Tuple[str, str, str, str]]) -> int:
        """Bulk add or update SMTP accounts for ultra-fast loading"""
        if not accounts:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        added = 0
        try:
            for email, pwd, tok, cid in accounts:
                cursor.execute("""
                    INSERT INTO smtp_accounts (email, password, token, client_id, status)
                    VALUES (?, ?, ?, ?, 'ready')
                    ON CONFLICT(email) DO UPDATE SET
                        password=excluded.password,
                        token=excluded.token,
                        client_id=excluded.client_id,
                        status='ready'
                """, (email, pwd, tok, cid))
                added += 1
            conn.commit()
            return added
        finally:
            conn.close()
    
    def get_smtp_accounts(self, status: Optional[str] = None) -> List[Dict]:
        """Get SMTP accounts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM smtp_accounts WHERE status=? ORDER BY last_used ASC, emails_sent ASC", (status,))
        else:
            cursor.execute("SELECT * FROM smtp_accounts ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_smtp_status(self, email: str, status: str):
        """Update SMTP account status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE smtp_accounts SET status=? WHERE email=?", (status, email))
        conn.commit()
        conn.close()
        
    def update_smtp_token(self, email: str, token: str):
        """Update SMTP token (refresh token)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE smtp_accounts SET token=? WHERE email=?", (token, email))
        conn.commit()
        conn.close()
    
    def increment_smtp_sent(self, email: str):
        """Increment sent count for SMTP"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE smtp_accounts 
            SET emails_sent = emails_sent + 1, last_used = CURRENT_TIMESTAMP
            WHERE email = ?
        """, (email,))
        conn.commit()
        conn.close()
    
    def clear_smtp_accounts(self):
        """Clear all SMTP accounts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM smtp_accounts")
        conn.commit()
        conn.close()

    def reset_smtp_statuses(self):
        """Reset all SMTP accounts with error back to ready"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE smtp_accounts SET status='ready' WHERE status='error'")
        conn.commit()
        conn.close()
    
    # Recipients Methods
    def add_recipient(self, email: str, name: str = ""):
        """Add recipient"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recipients (email, name)
            VALUES (?, ?)
        """, (email, name))
        conn.commit()
        conn.close()
        
    def add_or_reset_recipient(self, email: str, name: str = "") -> bool:
        """Add recipient if not exists, or reset existing status to pending"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM recipients WHERE email=?", (email,))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE recipients 
                SET name=?, status='pending', error_message=NULL 
                WHERE email=?
            """, (name, email))
            is_new = False
        else:
            cursor.execute("""
                INSERT INTO recipients (email, name, status, error_message)
                VALUES (?, ?, 'pending', NULL)
            """, (email, name))
            is_new = True
        conn.commit()
        conn.close()
        return is_new

    def add_recipients_bulk(self, recipients_list: List[Tuple[str, str]]) -> int:
        """High-performance bulk insert of recipients in a single transaction (5k-10k in <0.1s)."""
        if not recipients_list:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        data = [(em, nm, 'pending', None) for em, nm in recipients_list]
        cursor.executemany("""
            INSERT INTO recipients (email, name, status, error_message)
            VALUES (?, ?, ?, ?)
        """, data)
        conn.commit()
        count = len(recipients_list)
        conn.close()
        return count
    
    def get_recipients(self, status: Optional[str] = None) -> List[Dict]:
        """Get recipients"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT * FROM recipients WHERE status=? ORDER BY created_at ASC", (status,))
        else:
            cursor.execute("SELECT * FROM recipients ORDER BY created_at DESC")
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_recipients(self) -> List[Dict]:
        """Alias for get_recipients()"""
        return self.get_recipients()
    
    def update_recipient_status(self, recipient_id: int, status: str, smtp_email: str = None, error_message: str = None):
        """Update recipient status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if status == 'sent':
            cursor.execute("""
                UPDATE recipients 
                SET status=?, sent_at=CURRENT_TIMESTAMP, smtp_email=?
                WHERE id=?
            """, (status, smtp_email, recipient_id))
        else:
            cursor.execute("""
                UPDATE recipients 
                SET status=?, error_message=?
                WHERE id=?
            """, (status, error_message, recipient_id))
        
        conn.commit()
        conn.close()
    
    def delete_recipient(self, recipient_id: int):
        """Delete recipient (for auto-removal after sending)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recipients WHERE id=?", (recipient_id,))
        conn.commit()
        conn.close()
    
    def clear_recipients(self):
        """Clear all recipients"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recipients")
        conn.commit()
        conn.close()
    
    # Send Logs Methods
    def add_send_log(self, recipient_email: str, smtp_email: str, status: str, 
                     error_code: int = None, error_message: str = None):
        """Add send log"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO send_logs (recipient_email, smtp_email, status, error_code, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (recipient_email, smtp_email, status, error_code, error_message))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Total SMTP
        cursor.execute("SELECT COUNT(*) FROM smtp_accounts")
        total_smtp = cursor.fetchone()[0]
        
        # Total Recipients
        cursor.execute("SELECT COUNT(*) FROM recipients")
        total_recipients = cursor.fetchone()[0]
        
        # Pending Recipients
        cursor.execute("SELECT COUNT(*) FROM recipients WHERE status='pending'")
        pending_recipients = cursor.fetchone()[0]
        
        # Sent today
        cursor.execute("""
            SELECT COUNT(*) FROM send_logs 
            WHERE date(sent_at) = date('now') AND status='sent'
        """)
        sent_today = cursor.fetchone()[0]
        
        # Success rate
        cursor.execute("SELECT COUNT(*) FROM send_logs WHERE status='sent'")
        success = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM send_logs")
        total = cursor.fetchone()[0]
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        conn.close()
        
        return {
            'total_smtp': total_smtp,
            'total_recipients': total_recipients,
            'pending_recipients': pending_recipients,
            'sent_today': sent_today,
            'success_rate': round(success_rate, 1)
        }

    # Settings Helpers
    def set_setting(self, key: str, value: str):
        """Set a persistent configuration value"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()

    def get_setting(self, key: str, default: str = "") -> str:
        """Get a persistent configuration value"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default

    # Templates Helpers
    def add_template(self, filename: str, content: str):
        """Add or update an HTML template"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO templates (filename, content) VALUES (?, ?)", (filename, content))
        conn.commit()
        conn.close()

    def get_templates(self) -> List[Dict]:
        """Get all HTML templates"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM templates ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def clear_templates(self):
        """Clear all HTML templates"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM templates")
        conn.commit()
        conn.close()

    # Subjects Helpers
    def add_subject(self, subject: str):
        """Add a subject line"""
        if not subject.strip():
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO subjects (subject) VALUES (?)", (subject.strip(),))
            conn.commit()
        finally:
            conn.close()

    def get_subjects(self) -> List[str]:
        """Get all subject lines"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT subject FROM subjects ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [row['subject'] for row in rows]

    def clear_subjects(self):
        """Clear all subject lines"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM subjects")
        conn.commit()
        conn.close()

    # Sender Names Helpers
    def add_sender_name(self, name: str):
        """Add a sender name"""
        if not name.strip():
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO sender_names (name) VALUES (?)", (name.strip(),))
            conn.commit()
        finally:
            conn.close()

    def get_sender_names(self) -> List[str]:
        """Get all sender names"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sender_names ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        return [row['name'] for row in rows]

    def clear_sender_names(self):
        """Clear all sender names"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sender_names")
        conn.commit()
        conn.close()


        # ── Unsubscribed Recipients Helpers ─────────────────────────────────────────
    @staticmethod
    def _normalize_utc_ts(ts: Optional[str]) -> str:
        """Normalize a timestamp string to 'YYYY-MM-DD HH:MM:SS' for safe chronological comparison."""
        if not ts:
            return ""
        clean = str(ts).strip().replace("T", " ")
        if clean.endswith("Z"):
            clean = clean[:-1]
        if "+" in clean:
            clean = clean.split("+", 1)[0]
        if "." in clean:
            clean = clean.split(".", 1)[0]
        return clean.strip()[:19]

    def add_unsubscribed(
        self,
        email: str,
        unsubscribed_at: Optional[str] = None,
        respect_removal: bool = False,
    ) -> bool:
        """Add an email to the unsubscribed suppression list with optional timestamp.

        When `respect_removal=True` (used by automated cloud/inbox sync), an email
        previously removed by the user is NOT re-added unless `unsubscribed_at`
        represents a newer unsubscribe event occurring after the removed record.
        """
        clean_email = (email or "").strip().lower()
        if not clean_email:
            return False
        norm_event_ts = self._normalize_utc_ts(unsubscribed_at)

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if respect_removal:
                cursor.execute(
                    "SELECT suppressed_unsub_at, removed_at FROM removed_unsubscribes WHERE LOWER(email) = ?",
                    (clean_email,),
                )
                rem_row = cursor.fetchone()
                if rem_row:
                    prev_unsub = self._normalize_utc_ts(rem_row["suppressed_unsub_at"])
                    removed_at = self._normalize_utc_ts(rem_row["removed_at"])
                    cutoff = max(prev_unsub, removed_at)
                    if norm_event_ts and cutoff and norm_event_ts > cutoff:
                        # Genuinely new unsubscribe click after user removed the contact
                        cursor.execute(
                            "DELETE FROM removed_unsubscribes WHERE LOWER(email) = ?",
                            (clean_email,),
                        )
                    else:
                        return False
            else:
                # Explicit manual addition by user clears any prior removal tombstone
                cursor.execute(
                    "DELETE FROM removed_unsubscribes WHERE LOWER(email) = ?",
                    (clean_email,),
                )

            if norm_event_ts:
                cursor.execute(
                    "INSERT OR IGNORE INTO unsubscribed_recipients (email, unsubscribed_at) VALUES (?, ?)",
                    (clean_email, norm_event_ts),
                )
            else:
                cursor.execute(
                    "INSERT OR IGNORE INTO unsubscribed_recipients (email) VALUES (?)",
                    (clean_email,),
                )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
        finally:
            conn.close()

    def remove_unsubscribed(self, email: str) -> bool:
        """Remove a single email from local suppression list and record a removal tombstone."""
        clean_email = (email or "").strip().lower()
        if not clean_email:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT unsubscribed_at FROM unsubscribed_recipients WHERE LOWER(email) = ?",
                (clean_email,),
            )
            row = cursor.fetchone()
            prev_ts = self._normalize_utc_ts(row["unsubscribed_at"]) if row else ""

            cursor.execute(
                "DELETE FROM unsubscribed_recipients WHERE LOWER(email) = ?",
                (clean_email,),
            )
            deleted = cursor.rowcount > 0
            cursor.execute(
                """
                INSERT INTO removed_unsubscribes (email, suppressed_unsub_at, removed_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(email) DO UPDATE SET
                    suppressed_unsub_at = CASE
                        WHEN excluded.suppressed_unsub_at != '' THEN excluded.suppressed_unsub_at
                        ELSE removed_unsubscribes.suppressed_unsub_at
                    END,
                    removed_at = CURRENT_TIMESTAMP
                """,
                (clean_email, prev_ts),
            )
            conn.commit()
            return deleted
        finally:
            conn.close()

    def clear_all_unsubscribed(self) -> int:
        """Clear all local unsubscribed contacts and record tombstones so sync does not resurrect them."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT email, unsubscribed_at FROM unsubscribed_recipients")
            existing = cursor.fetchall()
            for r in existing:
                em = (r["email"] or "").strip().lower()
                if not em:
                    continue
                prev_ts = self._normalize_utc_ts(r["unsubscribed_at"])
                cursor.execute(
                    """
                    INSERT INTO removed_unsubscribes (email, suppressed_unsub_at, removed_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(email) DO UPDATE SET
                        suppressed_unsub_at = CASE
                            WHEN excluded.suppressed_unsub_at != '' THEN excluded.suppressed_unsub_at
                            ELSE removed_unsubscribes.suppressed_unsub_at
                        END,
                        removed_at = CURRENT_TIMESTAMP
                    """,
                    (em, prev_ts),
                )
            cursor.execute("DELETE FROM unsubscribed_recipients")
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()

    def is_unsubscribed(self, email: str) -> bool:
        """Check if an email is unsubscribed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM unsubscribed_recipients WHERE LOWER(email) = ?",
            (email.strip().lower(),)
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def get_unsubscribed_list(self) -> List[Dict]:
        """Get all unsubscribed contacts."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email, datetime(unsubscribed_at, 'localtime') as unsubscribed_at FROM unsubscribed_recipients ORDER BY unsubscribed_at DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def is_unsub_message_processed(self, msg_id: str) -> bool:
        """Check whether an inbox unsubscribe message ID has already been processed."""
        if not msg_id:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM processed_unsub_messages WHERE msg_id = ?", (msg_id,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def mark_unsub_message_processed(self, msg_id: str, sender_email: str, unsub_email: str):
        """Record an inbox unsubscribe message ID as processed."""
        if not msg_id:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO processed_unsub_messages (msg_id, sender_email, unsub_email) VALUES (?, ?, ?)",
                (msg_id, (sender_email or "").strip().lower(), (unsub_email or "").strip().lower())
            )
            conn.commit()
        finally:
            conn.close()

    def get_active_smtp_for_unsub_sync(self, limit: int = 15) -> List[Dict]:
        """Return active SMTP accounts prioritized by most recent usage for inbox unsubscribe polling."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM smtp_accounts
                WHERE status != 'expired' AND token IS NOT NULL AND token != ''
                ORDER BY
                    CASE WHEN last_used IS NOT NULL THEN 0 ELSE 1 END ASC,
                    last_used DESC,
                    emails_sent DESC,
                    id ASC
                LIMIT ?
            """, (int(limit),))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Global Campaign Clear Helper ───────────────────────────────────────────
    def clear_all_campaign_data(self):
        """
        Clears all campaign data across the database:
        - Recipients
        - SMTP accounts
        - Send logs
        - Templates
        - Subjects
        - Sender names
        - Task settings (preserves 'license_token')
        
        Strictly preserves:
        - license_token (stays licensed)
        - unsubscribed_recipients (suppression list is retained)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM recipients")
            cursor.execute("DELETE FROM smtp_accounts")
            cursor.execute("DELETE FROM send_logs")
            cursor.execute("DELETE FROM templates")
            cursor.execute("DELETE FROM subjects")
            cursor.execute("DELETE FROM sender_names")
            cursor.execute("DELETE FROM settings WHERE key != 'license_token'")
            try:
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('recipients', 'smtp_accounts', 'send_logs', 'templates', 'subjects', 'sender_names')")
            except Exception:
                pass
            conn.commit()
        finally:
            conn.close()

