from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import BaseDocument
from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenUsageRecord(BaseDocument):
    """Track token usage for cost monitoring and optimization"""
    user_id: str
    session_id: str
    request_type: str  # "tutoring", "code_analysis", "hint_generation", etc.
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    response_time_ms: float
    success: bool
    error_type: Optional[str] = None


class TokenTracker:
    """Service for tracking and analyzing AI token usage"""
    
    def __init__(self):
        self.db = None
        # Pricing per 1M tokens (approximate as of 2024)
        self.model_pricing = {
            "gpt-4o-mini": {
                "input": 0.15,   # $0.15 per 1M input tokens
                "output": 0.60   # $0.60 per 1M output tokens
            },
            "gpt-4": {
                "input": 30.0,   # $30 per 1M input tokens  
                "output": 60.0   # $60 per 1M output tokens
            },
            "gpt-3.5-turbo": {
                "input": 0.50,   # $0.50 per 1M input tokens
                "output": 1.50   # $1.50 per 1M output tokens
            }
        }
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def calculate_cost(
        self, 
        model: str, 
        prompt_tokens: int, 
        completion_tokens: int
    ) -> float:
        """Calculate estimated cost for token usage"""
        
        pricing = self.model_pricing.get(model, self.model_pricing["gpt-4o-mini"])
        
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def record_usage(
        self,
        user_id: str,
        session_id: str,
        request_type: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        response_time_ms: float,
        success: bool = True,
        error_type: Optional[str] = None
    ) -> TokenUsageRecord:
        """Record token usage for monitoring and billing"""
        
        db = await self._get_db()
        
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = self.calculate_cost(model, prompt_tokens, completion_tokens)
        
        record = TokenUsageRecord(
            user_id=user_id,
            session_id=session_id,
            request_type=request_type,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            response_time_ms=response_time_ms,
            success=success,
            error_type=error_type
        )
        
        result = await db.token_usage.insert_one(record.dict(by_alias=True))
        record.id = result.inserted_id
        
        logger.info(f"Recorded token usage: {total_tokens} tokens, ${estimated_cost:.4f}")
        return record
    
    async def get_user_usage_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get token usage summary for a user over specified days"""
        
        db = await self._get_db()
        start_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "created_at": {"$gte": start_date},
                    "success": True
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_requests": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_prompt_tokens": {"$sum": "$prompt_tokens"},
                    "total_completion_tokens": {"$sum": "$completion_tokens"},
                    "total_cost": {"$sum": "$estimated_cost_usd"},
                    "avg_tokens_per_request": {"$avg": "$total_tokens"},
                    "avg_response_time": {"$avg": "$response_time_ms"}
                }
            }
        ]
        
        result = await db.token_usage.aggregate(pipeline).to_list(1)
        
        if result:
            summary = result[0]
            summary["period_days"] = days
            summary["daily_average_cost"] = summary["total_cost"] / days if days > 0 else 0
            summary["cost_per_token"] = summary["total_cost"] / summary["total_tokens"] if summary["total_tokens"] > 0 else 0
            return summary
        
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost": 0.0,
            "avg_tokens_per_request": 0,
            "avg_response_time": 0,
            "period_days": days,
            "daily_average_cost": 0.0,
            "cost_per_token": 0.0
        }
    
    async def get_session_usage(self, session_id: str) -> Dict[str, Any]:
        """Get token usage for a specific session"""
        
        db = await self._get_db()
        
        pipeline = [
            {"$match": {"session_id": session_id}},
            {
                "$group": {
                    "_id": "$request_type",
                    "count": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost": {"$sum": "$estimated_cost_usd"},
                    "avg_response_time": {"$avg": "$response_time_ms"},
                    "success_rate": {"$avg": {"$cond": ["$success", 1, 0]}}
                }
            }
        ]
        
        results = await db.token_usage.aggregate(pipeline).to_list(100)
        
        # Aggregate totals
        session_summary = {
            "by_request_type": {},
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_response_time": 0,
            "overall_success_rate": 0
        }
        
        total_response_time = 0
        total_successes = 0
        
        for result in results:
            request_type = result["_id"]
            session_summary["by_request_type"][request_type] = {
                "count": result["count"],
                "total_tokens": result["total_tokens"],
                "total_cost": result["total_cost"],
                "avg_response_time": result["avg_response_time"],
                "success_rate": result["success_rate"]
            }
            
            session_summary["total_requests"] += result["count"]
            session_summary["total_tokens"] += result["total_tokens"]
            session_summary["total_cost"] += result["total_cost"]
            total_response_time += result["avg_response_time"] * result["count"]
            total_successes += result["success_rate"] * result["count"]
        
        if session_summary["total_requests"] > 0:
            session_summary["avg_response_time"] = total_response_time / session_summary["total_requests"]
            session_summary["overall_success_rate"] = total_successes / session_summary["total_requests"]
        
        return session_summary
    
    async def get_system_usage_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get system-wide usage statistics"""
        
        db = await self._get_db()
        start_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "model": "$model",
                        "request_type": "$request_type"
                    },
                    "requests": {"$sum": 1},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost": {"$sum": "$estimated_cost_usd"},
                    "failures": {"$sum": {"$cond": ["$success", 0, 1]}}
                }
            },
            {
                "$group": {
                    "_id": "$_id.date",
                    "daily_requests": {"$sum": "$requests"},
                    "daily_tokens": {"$sum": "$total_tokens"},
                    "daily_cost": {"$sum": "$total_cost"},
                    "daily_failures": {"$sum": "$failures"},
                    "by_model": {
                        "$push": {
                            "model": "$_id.model",
                            "request_type": "$_id.request_type",
                            "requests": "$requests",
                            "tokens": "$total_tokens",
                            "cost": "$total_cost"
                        }
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        results = await db.token_usage.aggregate(pipeline).to_list(days + 5)
        
        return {
            "period_days": days,
            "daily_stats": results,
            "total_days_with_data": len(results)
        }
    
    async def get_cost_alerts(self, user_id: str) -> List[Dict[str, Any]]:
        """Check for cost-related alerts for a user"""
        
        alerts = []
        
        # Check daily usage
        daily_summary = await self.get_user_usage_summary(user_id, days=1)
        if daily_summary["total_cost"] > 1.0:  # $1 per day threshold
            alerts.append({
                "type": "high_daily_cost",
                "message": f"High daily cost: ${daily_summary['total_cost']:.2f}",
                "severity": "warning",
                "cost": daily_summary["total_cost"]
            })
        
        # Check token efficiency
        if daily_summary["avg_tokens_per_request"] > 2000:  # High token usage per request
            alerts.append({
                "type": "high_token_usage",
                "message": f"High average tokens per request: {daily_summary['avg_tokens_per_request']:.0f}",
                "severity": "info",
                "avg_tokens": daily_summary["avg_tokens_per_request"]
            })
        
        # Check monthly trend
        monthly_summary = await self.get_user_usage_summary(user_id, days=30)
        if monthly_summary["total_cost"] > 10.0:  # $10 per month threshold
            alerts.append({
                "type": "high_monthly_cost",
                "message": f"High monthly cost: ${monthly_summary['total_cost']:.2f}",
                "severity": "warning",
                "cost": monthly_summary["total_cost"]
            })
        
        return alerts
    
    async def optimize_context_usage(self, session_id: str) -> Dict[str, Any]:
        """Analyze session for context optimization opportunities"""
        
        db = await self._get_db()
        
        # Get recent usage patterns for this session
        recent_usage = await db.token_usage.find({
            "session_id": session_id
        }).sort("created_at", -1).limit(10).to_list(10)
        
        if not recent_usage:
            return {"recommendations": [], "current_efficiency": "unknown"}
        
        recommendations = []
        total_tokens = sum(record["total_tokens"] for record in recent_usage)
        avg_prompt_tokens = sum(record["prompt_tokens"] for record in recent_usage) / len(recent_usage)
        
        # Check for context bloat
        if avg_prompt_tokens > 1500:
            recommendations.append({
                "type": "reduce_context",
                "message": "Consider context compression - average prompt size is high",
                "current_avg_prompt_tokens": avg_prompt_tokens,
                "suggested_max": 1000
            })
        
        # Check response efficiency  
        avg_completion_tokens = sum(record["completion_tokens"] for record in recent_usage) / len(recent_usage)
        if avg_completion_tokens > 500:
            recommendations.append({
                "type": "reduce_response_length",
                "message": "AI responses are quite lengthy - consider shorter responses",
                "current_avg_completion_tokens": avg_completion_tokens,
                "suggested_max": 300
            })
        
        # Efficiency score (lower token usage per request is better)
        efficiency_score = "good" if avg_prompt_tokens + avg_completion_tokens < 1000 else "poor"
        
        return {
            "recommendations": recommendations,
            "current_efficiency": efficiency_score,
            "total_tokens_analyzed": total_tokens,
            "avg_prompt_tokens": avg_prompt_tokens,
            "avg_completion_tokens": avg_completion_tokens
        }


# Global instance
token_tracker = TokenTracker()