"""
Database manager for storing SMTP accounts and recipients
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class Database:
    """SQLite database manager"""
    
    def __init__(self, db_path: str = "data/mailer.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
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

