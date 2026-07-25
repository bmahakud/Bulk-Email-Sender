"""
Attachment processing and base64 conversion
"""
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger


class AttachmentProcessor:
    """Process attachments for email sending"""
    
    # Max attachment size: 3MB per attachment (Graph API limit is 4MB)
    MAX_SIZE = 3 * 1024 * 1024
    
    MIME_TYPES = {
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.html': 'text/html',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.zip': 'application/zip'
    }
    
    @staticmethod
    def process_attachment(file_path: Path) -> Optional[Dict]:
        """
        Process a single attachment file
        
        Args:
            file_path: Path to attachment file
            
        Returns:
            Dict with attachment data ready for Graph API or None if error
        """
        try:
            if not file_path.exists():
                logger.error(f"Attachment file not found: {file_path}")
                return None
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > AttachmentProcessor.MAX_SIZE:
                logger.error(f"Attachment too large: {file_path} ({file_size} bytes)")
                return None
            
            # Read file as binary
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Convert to base64
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            # Get MIME type
            ext = file_path.suffix.lower()
            mime_type = AttachmentProcessor.MIME_TYPES.get(ext, 'application/octet-stream')
            
            # Build attachment object for Graph API
            attachment = {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": file_path.name,
                "contentType": mime_type,
                "contentBytes": base64_data
            }
            
            logger.info(f"Processed attachment: {file_path.name} ({file_size} bytes)")
            return attachment
            
        except Exception as e:
            logger.error(f"Error processing attachment {file_path}: {e}")
            return None
    
    @staticmethod
    def process_attachments(file_paths: List[Path]) -> List[Dict]:
        """Process multiple attachments"""
        attachments = []
        
        for file_path in file_paths:
            attachment = AttachmentProcessor.process_attachment(file_path)
            if attachment:
                attachments.append(attachment)
        
        return attachments
    
    @staticmethod
    def validate_attachment(file_path: Path) -> Tuple[bool, str]:
        """
        Validate attachment file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"
        
        if not file_path.is_file():
            return False, f"Not a file: {file_path}"
        
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False, f"File is empty: {file_path}"
        
        if file_size > AttachmentProcessor.MAX_SIZE:
            return False, f"File too large: {file_path} (max 3MB)"
        
        return True, ""
