"""
Database models and initialization
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from loguru import logger


DB_PATH = Path("database/database.db")


def get_connection():
    """Get database connection"""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database with all tables"""
    logger.info("Initializing database")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at REAL,
            status TEXT DEFAULT 'active',
            daily_sent INTEGER DEFAULT 0,
            total_sent INTEGER DEFAULT 0,
            last_used REAL,
            created_at REAL DEFAULT (julianday('now')),
            UNIQUE(email)
        )
    """)
    
    # Recipients table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            name TEXT,
            company TEXT,
            invoice TEXT,
            custom_tags TEXT,
            status TEXT DEFAULT 'pending',
            campaign_id INTEGER,
            created_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            subject TEXT,
            html_path TEXT,
            html_content TEXT,
            attachment_paths TEXT,
            created_at REAL DEFAULT (julianday('now')),
            updated_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Subject lines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subject_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            campaign_id INTEGER,
            usage_count INTEGER DEFAULT 0,
            created_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Campaigns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            template_id INTEGER,
            status TEXT DEFAULT 'draft',
            total_recipients INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            settings TEXT,
            created_at REAL DEFAULT (julianday('now')),
            started_at REAL,
            completed_at REAL,
            FOREIGN KEY (template_id) REFERENCES templates(id)
        )
    """)
    
    # Send logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS send_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            recipient_email TEXT NOT NULL,
            account_email TEXT NOT NULL,
            subject TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            response_code INTEGER,
            retry_count INTEGER DEFAULT 0,
            sent_at REAL DEFAULT (julianday('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    """)
    
    # Retry queue table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS retry_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            recipient_id INTEGER,
            recipient_email TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            next_retry_at REAL,
            created_at REAL DEFAULT (julianday('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
            FOREIGN KEY (recipient_id) REFERENCES recipients(id)
        )
    """)
    
    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at REAL DEFAULT (julianday('now'))
        )
    """)
    
    # Crash recovery table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crash_recovery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            state TEXT,
            last_recipient_id INTEGER,
            created_at REAL DEFAULT (julianday('now')),
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")


class Account:
    """Account model"""
    
    @staticmethod
    def create(email: str) -> int:
        """Create new account"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (email, status) VALUES (?, ?)",
            (email, 'pending')
        )
        account_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return account_id
    
    @staticmethod
    def update_tokens(email: str, access_token: str, refresh_token: str, expires_at: float):
        """Update account tokens"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET access_token = ?, refresh_token = ?, token_expires_at = ?, status = 'active'
            WHERE email = ?
        """, (access_token, refresh_token, expires_at, email))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_all() -> List[Dict]:
        """Get all accounts"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_active() -> List[Dict]:
        """Get active accounts with valid tokens"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM accounts 
            WHERE status = 'active' AND access_token IS NOT NULL
            ORDER BY last_used ASC, daily_sent ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def increment_sent(email: str):
        """Increment send count"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET daily_sent = daily_sent + 1, 
                total_sent = total_sent + 1,
                last_used = julianday('now')
            WHERE email = ?
        """, (email,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def update_status(email: str, status: str):
        """Update account status"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET status = ? WHERE email = ?", (status, email))
        conn.commit()
        conn.close()


class Recipient:
    """Recipient model"""
    
    @staticmethod
    def bulk_insert(recipients: List[Dict], campaign_id: Optional[int] = None):
        """Bulk insert recipients"""
        conn = get_connection()
        cursor = conn.cursor()
        for r in recipients:
            cursor.execute("""
                INSERT INTO recipients (email, name, company, invoice, custom_tags, campaign_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                r.get('email'),
                r.get('name'),
                r.get('company'),
                r.get('invoice'),
                r.get('custom_tags'),
                campaign_id
            ))
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_by_campaign(campaign_id: int) -> List[Dict]:
        """Get recipients by campaign"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM recipients WHERE campaign_id = ? AND status = 'pending'",
            (campaign_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def update_status(recipient_id: int, status: str):
        """Update recipient status"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE recipients SET status = ? WHERE id = ?",
            (status, recipient_id)
        )
        conn.commit()
        conn.close()


class Campaign:
    """Campaign model"""
    
    @staticmethod
    def create(name: str, template_id: Optional[int] = None) -> int:
        """Create new campaign"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO campaigns (name, template_id, status)
            VALUES (?, ?, 'draft')
        """, (name, template_id))
        campaign_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return campaign_id
    
    @staticmethod
    def update_status(campaign_id: int, status: str):
        """Update campaign status"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE campaigns SET status = ? WHERE id = ?",
            (status, campaign_id)
        )
        conn.commit()
        conn.close()
    
    @staticmethod
    def increment_sent(campaign_id: int):
        """Increment sent count"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE campaigns SET sent_count = sent_count + 1 WHERE id = ?
        """, (campaign_id,))
        conn.commit()
        conn.close()
    
    @staticmethod
    def increment_failed(campaign_id: int):
        """Increment failed count"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE campaigns SET failed_count = failed_count + 1 WHERE id = ?
        """, (campaign_id,))
        conn.commit()
        conn.close()


class SendLog:
    """Send log model"""
    
    @staticmethod
    def create(campaign_id: int, recipient_email: str, account_email: str, 
               subject: str, status: str, error_message: Optional[str] = None,
               response_code: Optional[int] = None):
        """Create send log"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO send_logs 
            (campaign_id, recipient_email, account_email, subject, status, error_message, response_code)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (campaign_id, recipient_email, account_email, subject, status, error_message, response_code))
        conn.commit()
        conn.close()
