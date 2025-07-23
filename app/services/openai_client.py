from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime
import openai
from openai import AsyncOpenAI
import tiktoken

from app.core.config import settings
from app.models import ConversationMessage, MessageType

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client with error handling and cost tracking"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_REQUEST_TIMEOUT
        )
        self.tokenizer = tiktoken.encoding_for_model(settings.OPENAI_MODEL)
        self.total_tokens_used = 0
        self.total_requests_made = 0
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            # Fallback: rough estimate (4 characters per token)
            return len(text) // 4
    
    def format_messages_for_openai(
        self, 
        messages: List[ConversationMessage],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Convert ConversationMessage objects to OpenAI format"""
        
        openai_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            openai_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Convert conversation messages
        for msg in messages:
            role = "assistant" if msg.message_type == MessageType.ASSISTANT else "user"
            openai_messages.append({
                "role": role,
                "content": msg.content
            })
        
        return openai_messages
    
    async def generate_response(
        self,
        messages: List[ConversationMessage],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate AI response with error handling and token tracking"""
        
        try:
            # Format messages for OpenAI
            openai_messages = self.format_messages_for_openai(messages, system_prompt)
            
            # Set default parameters
            model = model or settings.OPENAI_MODEL
            max_tokens = max_tokens or settings.OPENAI_MAX_TOKENS
            temperature = temperature or settings.OPENAI_TEMPERATURE
            
            # Count input tokens
            input_text = "\n".join([msg["content"] for msg in openai_messages])
            input_tokens = self.count_tokens(input_text)
            
            logger.info(f"Making OpenAI request with {input_tokens} input tokens")
            
            # Make API request
            response = await self.client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                presence_penalty=0.0,
                frequency_penalty=0.0,
            )
            
            # Extract response data
            response_content = response.choices[0].message.content
            usage = response.usage
            
            # Update tracking
            self.total_tokens_used += usage.total_tokens
            self.total_requests_made += 1
            
            logger.info(f"OpenAI response generated: {usage.total_tokens} tokens used")
            
            return {
                "success": True,
                "content": response_content,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                },
                "model": model,
                "finish_reason": response.choices[0].finish_reason
            }
            
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            await asyncio.sleep(1)  # Brief delay before retry
            return {
                "success": False,
                "error": "rate_limit",
                "message": "API rate limit exceeded. Please try again shortly.",
                "retry_after": 60
            }
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            return {
                "success": False,
                "error": "api_error",
                "message": "AI service is temporarily unavailable. Please try again.",
                "details": str(e)
            }
            
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}")
            return {
                "success": False,
                "error": "connection_error",
                "message": "Unable to connect to AI service. Please check your connection.",
                "details": str(e)
            }
            
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {e}")
            return {
                "success": False,
                "error": "auth_error",
                "message": "AI service authentication failed.",
                "details": str(e)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI request: {e}")
            return {
                "success": False,
                "error": "unknown_error",
                "message": "An unexpected error occurred. Please try again.",
                "details": str(e)
            }
    
    async def generate_response_with_retry(
        self,
        messages: List[ConversationMessage],
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response with automatic retry logic"""
        
        last_error = None
        
        for attempt in range(max_retries):
            if attempt > 0:
                wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                logger.info(f"Retrying OpenAI request (attempt {attempt + 1}) after {wait_time}s")
                await asyncio.sleep(wait_time)
            
            result = await self.generate_response(messages, system_prompt, **kwargs)
            
            if result["success"]:
                if attempt > 0:
                    logger.info(f"OpenAI request succeeded on attempt {attempt + 1}")
                return result
            
            last_error = result
            
            # Don't retry on certain errors
            if result.get("error") in ["auth_error", "invalid_request"]:
                break
            
            # For rate limits, respect the retry_after if provided
            if result.get("error") == "rate_limit" and result.get("retry_after"):
                await asyncio.sleep(min(result["retry_after"], 60))
        
        logger.error(f"OpenAI request failed after {max_retries} attempts")
        return last_error or {
            "success": False,
            "error": "max_retries_exceeded",
            "message": "AI service is currently unavailable after multiple attempts."
        }
    
    async def analyze_code_submission(
        self,
        code: str,
        problem_description: str,
        expected_output: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze a code submission for correctness and provide feedback"""
        
        system_prompt = """You are an expert Python programming tutor. Analyze the student's code submission and provide constructive feedback.

Your analysis should include:
1. Whether the code is syntactically correct
2. Whether it solves the problem correctly
3. Code quality and style observations
4. Suggestions for improvement
5. If incorrect, gentle hints toward the solution

Be encouraging and educational in your feedback."""

        user_prompt = f"""Problem Description:
{problem_description}

Student's Code:
```python
{code}
```

Expected Output (if available):
{expected_output or "Not specified"}

Please analyze this code submission and provide feedback."""

        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        return await self.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent analysis
        )
    
    async def generate_hint(
        self,
        problem_description: str,
        student_attempts: List[str],
        hint_level: int = 1
    ) -> Dict[str, Any]:
        """Generate a progressive hint for a struggling student"""
        
        system_prompt = f"""You are a patient Python programming tutor. The student is stuck on a problem and needs a hint.

Hint Level {hint_level} Guidelines:
- Level 1: Give a conceptual hint about the approach
- Level 2: Suggest specific Python concepts or functions to use
- Level 3: Provide a more detailed hint with partial code structure
- Level 4: Give a nearly complete solution with blanks to fill

Be encouraging and guide them toward the solution without giving it away completely."""

        attempts_text = "\n\n".join([f"Attempt {i+1}:\n```python\n{code}\n```" 
                                   for i, code in enumerate(student_attempts)])
        
        user_prompt = f"""Problem Description:
{problem_description}

Student's Previous Attempts:
{attempts_text}

The student needs a level {hint_level} hint. Please provide appropriate guidance."""

        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        return await self.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.4
        )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        return {
            "total_tokens_used": self.total_tokens_used,
            "total_requests_made": self.total_requests_made,
            "estimated_cost_usd": self.estimate_cost(),
            "model": settings.OPENAI_MODEL
        }
    
    def estimate_cost(self) -> float:
        """Estimate cost based on token usage (rough estimate)"""
        # GPT-4o-mini pricing (as of 2024): ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
        # Using average estimate of $0.30 per 1M tokens
        cost_per_million_tokens = 0.30
        return (self.total_tokens_used / 1_000_000) * cost_per_million_tokens


# Global instance
openai_client = OpenAIClient()