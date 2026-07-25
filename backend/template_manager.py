"""
Template Manager - Handle HTML, images, PDF attachments with base64 encoding
"""
import base64
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image
import io


class TemplateManager:
    """Manage email templates with HTML, images, and attachments"""
    
    def __init__(self):
        self.templates = []
        self.current_template_index = 0
    
    def process_html_inline_images(self, html_content: str, html_file_path: str = None) -> str:
        """
        Convert all images in HTML to base64 inline images
        Finds <img src="..."> and converts to <img src="data:image/...;base64,...">
        """
        if not html_file_path:
            return html_content
        
        html_dir = Path(html_file_path).parent
        
        # Find all img tags with src
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        
        def replace_image(match):
            img_src = match.group(1)
            
            # Skip if already base64
            if img_src.startswith('data:'):
                return match.group(0)
            
            # Skip if URL
            if img_src.startswith('http'):
                return match.group(0)
            
            # Local file - convert to base64
            try:
                img_path = html_dir / img_src
                if img_path.exists():
                    base64_img = self.image_to_base64(str(img_path))
                    if base64_img:
                        return match.group(0).replace(img_src, base64_img)
            except Exception:
                pass
            
            return match.group(0)
        
        return re.sub(img_pattern, replace_image, html_content)
    
    def image_to_base64(self, image_path: str) -> Optional[str]:
        """
        Convert image to base64 data URI
        Supports: GIF, PNG, JPEG, JPG, WEBP
        """
        try:
            img_path = Path(image_path)
            
            # Get mime type
            ext = img_path.suffix.lower()
            mime_types = {
                '.gif': 'image/gif',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp'
            }
            
            mime_type = mime_types.get(ext, 'image/jpeg')
            
            # Read and encode
            with open(image_path, 'rb') as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')
                return f"data:{mime_type};base64,{base64_data}"
        
        except Exception as e:
            print(f"Error encoding image {image_path}: {e}")
            return None
    
    def pdf_to_base64(self, pdf_path: str) -> Optional[str]:
        """Convert PDF to base64 string"""
        try:
            with open(pdf_path, 'rb') as f:
                pdf_data = f.read()
                return base64.b64encode(pdf_data).decode('utf-8')
        except Exception as e:
            print(f"Error encoding PDF {pdf_path}: {e}")
            return None
    
    def generate_attachment_name(self, recipient_email: str, file_extension: str) -> str:
        """
        Generate attachment name: firstname + random number + extension
        Example: groupleeman4829.pdf or groupleeman4829.jpg
        """
        import random
        
        # Extract first part of email (before @)
        email_prefix = recipient_email.split('@')[0]
        
        # Generate random 4-digit number
        random_num = random.randint(1000, 9999)
        
        # Create filename
        return f"{email_prefix}{random_num}{file_extension}"
    
    def create_template(self, config: Dict) -> Dict:
        """
        Create email template with all options
        
        config: {
            'body_text': str (plain text body),
            'body_html': str (HTML content),
            'body_html_file': str (path to HTML file),
            'inline_images': bool (convert HTML images to base64),
            'attachment_images': List[str] (image file paths),
            'attachment_pdfs': List[str] (PDF file paths),
            'sender_name': str (optional, default uses SMTP email),
            'subject': str,
        }
        
        Returns template dict
        """
        template = {
            'body_text': config.get('body_text', ''),
            'body_html': config.get('body_html', ''),
            'sender_name': config.get('sender_name', ''),
            'subject': config.get('subject', 'Email Subject'),
            'attachments': []
        }
        
        # Process HTML with inline images
        if config.get('body_html_file'):
            html_file = config['body_html_file']
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            if config.get('inline_images', True):
                html_content = self.process_html_inline_images(html_content, html_file)
            
            template['body_html'] = html_content
        
        # Add image attachments (as base64)
        for img_path in config.get('attachment_images', []):
            base64_img = self.image_to_base64(img_path)
            if base64_img:
                ext = Path(img_path).suffix
                template['attachments'].append({
                    'type': 'image',
                    'data': base64_img,
                    'extension': ext,
                    'filename': Path(img_path).name
                })
        
        # Add PDF attachments (as base64)
        for pdf_path in config.get('attachment_pdfs', []):
            base64_pdf = self.pdf_to_base64(pdf_path)
            if base64_pdf:
                template['attachments'].append({
                    'type': 'pdf',
                    'data': base64_pdf,
                    'extension': '.pdf',
                    'filename': Path(pdf_path).name
                })
        
        return template
    
    def add_template(self, config: Dict):
        """Add a template to the rotation list"""
        template = self.create_template(config)
        self.templates.append(template)
    
    def get_next_template(self) -> Dict:
        """Get next template in rotation"""
        if not self.templates:
            return None
        
        template = self.templates[self.current_template_index]
        self.current_template_index = (self.current_template_index + 1) % len(self.templates)
        return template
    
    def clear_templates(self):
        """Clear all templates"""
        self.templates = []
        self.current_template_index = 0
    
    def get_template_count(self) -> int:
        """Get number of templates"""
        return len(self.templates)
    
    def replace_tags(self, text: str, tags: Dict) -> str:
        """
        Replace template tags with values
        
        tags: {
            'name': 'John Doe',
            'email': 'john@example.com',
            'tfn': '123456',
            'date': '2024-01-15',
            'time': '10:30 AM',
            ...
        }
        """
        for key, value in tags.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text
    
    def prepare_email_content(self, template: Dict, recipient: Dict, 
                            custom_tags: Dict = None) -> Dict:
        """
        Prepare final email content with tag replacement and attachments
        
        Returns: {
            'subject': str,
            'body': str (HTML or text),
            'sender_name': str,
            'attachments': List[Dict]
        }
        """
        # Build tags dictionary
        tags = {
            'name': recipient.get('name', ''),
            'email': recipient.get('email', ''),
            'firstname': recipient.get('email', '').split('@')[0],
        }
        
        # Add custom tags (TFN, Date, Time, etc.)
        if custom_tags:
            tags.update(custom_tags)
        
        # Replace tags in subject
        subject = self.replace_tags(template['subject'], tags)
        
        # Replace tags in body
        if template['body_html']:
            body = self.replace_tags(template['body_html'], tags)
        else:
            body = self.replace_tags(template['body_text'], tags)
        
        # Generate personalized attachment names
        attachments = []
        for att in template['attachments']:
            personalized_name = self.generate_attachment_name(
                recipient['email'], 
                att['extension']
            )
            attachments.append({
                'name': personalized_name,
                'data': att['data'],
                'type': att['type']
            })
        
        return {
            'subject': subject,
            'body': body,
            'sender_name': template.get('sender_name', ''),
            'attachments': attachments
        }


class SubjectLineManager:
    """Manage multiple subject lines with rotation"""
    
    def __init__(self):
        self.subject_lines = []
        self.current_index = 0
    
    def add_subject_line(self, subject: str):
        """Add a subject line"""
        if subject.strip():
            self.subject_lines.append(subject.strip())
    
    def add_bulk_subject_lines(self, subjects_text: str):
        """Add multiple subject lines from text (one per line)"""
        lines = subjects_text.strip().split('\n')
        for line in lines:
            self.add_subject_line(line)
    
    def get_next_subject(self) -> Optional[str]:
        """Get next subject line in rotation"""
        if not self.subject_lines:
            return None
        
        subject = self.subject_lines[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.subject_lines)
        return subject
    
    def clear(self):
        """Clear all subject lines"""
        self.subject_lines = []
        self.current_index = 0
    
    def get_count(self) -> int:
        """Get number of subject lines"""
        return len(self.subject_lines)


class SenderNameManager:
    """Manage multiple sender names with rotation"""
    
    def __init__(self):
        self.sender_names = []
        self.current_index = 0
        self.use_default = True
    
    def add_sender_name(self, name: str):
        """Add a sender name"""
        if name.strip():
            self.sender_names.append(name.strip())
            self.use_default = False
    
    def add_bulk_sender_names(self, names_text: str):
        """Add multiple sender names from text (one per line)"""
        lines = names_text.strip().split('\n')
        for line in lines:
            self.add_sender_name(line)
    
    def get_next_sender_name(self, default_email: str = None) -> str:
        """Get next sender name in rotation or default"""
        if self.use_default or not self.sender_names:
            return default_email or ''
        
        name = self.sender_names[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.sender_names)
        return name
    
    def set_use_default(self, use_default: bool):
        """Set whether to use default SMTP name"""
        self.use_default = use_default
    
    def clear(self):
        """Clear all sender names"""
        self.sender_names = []
        self.current_index = 0
        self.use_default = True
    
    def get_count(self) -> int:
        """Get number of sender names"""
        return len(self.sender_names)
