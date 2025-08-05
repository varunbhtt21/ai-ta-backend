"""
Response Formatter Utility
Basic beautification for AI-generated tutoring responses
"""

import re


class ResponseFormatter:
    """Utility class for basic beautification of AI-generated responses"""
    
    @staticmethod
    def format_tutoring_response(response_text: str) -> str:
        """
        Basic beautification of AI-generated responses (AI handles main formatting)
        
        Args:
            response_text: AI-generated response with built-in formatting
            
        Returns:
            Lightly cleaned response for frontend rendering
        """
        if not response_text or not response_text.strip():
            return response_text
        
        # Clean up the response
        formatted = response_text.strip()
        
        # Only apply basic beautification
        formatted = ResponseFormatter._clean_spacing(formatted)
        
        return formatted
    
    
    @staticmethod
    def _clean_spacing(text: str) -> str:
        """Clean up spacing while preserving AI-generated formatting"""
        
        # Only clean up excessive spacing, preserve intentional line breaks
        # Remove trailing spaces at end of lines
        text = re.sub(r' +$', '', text, flags=re.MULTILINE)
        
        # Clean up multiple consecutive empty lines (3+ becomes 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()


# Convenience function for easy importing
def format_response(response_text: str) -> str:
    """
    Basic beautification of AI-generated responses
    
    Args:
        response_text: AI-generated response with built-in formatting
        
    Returns:
        Lightly cleaned response for frontend rendering
    """
    return ResponseFormatter.format_tutoring_response(response_text)