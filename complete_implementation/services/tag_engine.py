"""
Tag replacement engine for dynamic content
"""
from datetime import datetime
from typing import Dict
import re
from loguru import logger


class TagEngine:
    """Replace tags in content with actual values"""
    
    # Default tags
    DEFAULT_TAGS = {
        "#DATE#": lambda: datetime.now().strftime("%Y-%m-%d"),
        "#TIME#": lambda: datetime.now().strftime("%H:%M:%S"),
        "#DATETIME#": lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "#YEAR#": lambda: datetime.now().strftime("%Y"),
        "#MONTH#": lambda: datetime.now().strftime("%B"),
        "#DAY#": lambda: datetime.now().strftime("%d"),
    }
    
    @staticmethod
    def replace_tags(content: str, recipient_data: Dict) -> str:
        """
        Replace tags in content with actual values
        
        Args:
            content: Content with tags (e.g., "Hello #EMAIL#")
            recipient_data: Dict with recipient info like {'email': 'test@example.com', 'name': 'John'}
            
        Returns:
            Content with tags replaced
        """
        result = content
        
        # Replace recipient-specific tags
        tag_map = {
            "#EMAIL#": recipient_data.get("email", ""),
            "#NAME#": recipient_data.get("name", ""),
            "#COMPANY#": recipient_data.get("company", ""),
            "#INVOICE#": recipient_data.get("invoice", ""),
        }
        
        # Add custom tags from recipient data
        if "custom_tags" in recipient_data and recipient_data["custom_tags"]:
            try:
                import json
                custom = json.loads(recipient_data["custom_tags"])
                for key, value in custom.items():
                    tag_map[f"#{key.upper()}#"] = str(value)
            except:
                pass
        
        # Replace recipient tags
        for tag, value in tag_map.items():
            result = result.replace(tag, value)
        
        # Replace default tags (date/time)
        for tag, func in TagEngine.DEFAULT_TAGS.items():
            if tag in result:
                result = result.replace(tag, func())
        
        return result
    
    @staticmethod
    def find_tags(content: str) -> list:
        """Find all tags in content"""
        return re.findall(r'#[A-Z_]+#', content)
    
    @staticmethod
    def validate_tags(content: str, recipient_data: Dict) -> list:
        """Validate that all tags can be replaced"""
        tags = TagEngine.find_tags(content)
        missing = []
        
        all_tags = {**TagEngine.DEFAULT_TAGS}
        all_tags.update({
            "#EMAIL#": True,
            "#NAME#": True,
            "#COMPANY#": True,
            "#INVOICE#": True,
        })
        
        for tag in tags:
            if tag not in all_tags and tag.replace("#", "").lower() not in recipient_data:
                missing.append(tag)
        
        return missing
