"""
Performance monitoring service for intelligent tutoring sessions.
Tracks session performance, response times, and system metrics.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import logging
from statistics import mean, median

from ..models.session import Session
from ..database.connection import get_database

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Individual performance metric data point"""
    timestamp: datetime
    session_id: str
    metric_type: str
    value: float
    metadata: Dict[str, Any]


@dataclass
class SessionPerformanceReport:
    """Comprehensive session performance report"""
    session_id: str
    user_id: str
    assignment_id: str
    session_start: datetime
    session_duration: float
    
    # Response time metrics
    avg_response_time: float
    median_response_time: float
    min_response_time: float
    max_response_time: float
    
    # Intelligence metrics
    compression_events: int
    compression_savings: float
    token_usage_total: int
    token_usage_avg: float
    
    # Teaching effectiveness metrics
    problem_completion_rate: float
    hint_usage_rate: float
    error_recovery_rate: float
    student_engagement_score: float
    
    # System performance
    memory_usage_peak: float
    cpu_usage_avg: float
    api_errors_count: int
    
    # AI model performance
    model_accuracy_score: float
    prompt_effectiveness_score: float
    adaptation_success_rate: float


class PerformanceMonitor:
    """
    Advanced performance monitoring for intelligent tutoring sessions.
    Tracks response times, system metrics, and teaching effectiveness.
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[PerformanceMetric]] = {}
        self.active_timers: Dict[str, float] = {}
        self.session_stats: Dict[str, Dict] = {}
    
    def start_timer(self, timer_id: str) -> None:
        """Start a performance timer"""
        self.active_timers[timer_id] = time.time()
    
    def end_timer(self, timer_id: str, session_id: str, metric_type: str, metadata: Optional[Dict] = None) -> float:
        """End a performance timer and record the metric"""
        if timer_id not in self.active_timers:
            logger.warning(f"Timer {timer_id} not found")
            return 0.0
        
        duration = time.time() - self.active_timers[timer_id]
        del self.active_timers[timer_id]
        
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            session_id=session_id,
            metric_type=metric_type,
            value=duration,
            metadata=metadata or {}
        )
        
        self.record_metric(metric)
        return duration
    
    def record_metric(self, metric: PerformanceMetric) -> None:
        """Record a performance metric"""
        if metric.session_id not in self.metrics:
            self.metrics[metric.session_id] = []
        
        self.metrics[metric.session_id].append(metric)
        
        # Update session stats
        if metric.session_id not in self.session_stats:
            self.session_stats[metric.session_id] = {
                'total_requests': 0,
                'total_response_time': 0,
                'compression_events': 0,
                'token_usage': 0,
                'errors': 0
            }
        
        stats = self.session_stats[metric.session_id]
        
        if metric.metric_type == 'response_time':
            stats['total_requests'] += 1
            stats['total_response_time'] += metric.value
        elif metric.metric_type == 'compression_event':
            stats['compression_events'] += 1
        elif metric.metric_type == 'token_usage':
            stats['token_usage'] += metric.value
        elif metric.metric_type == 'error':
            stats['errors'] += 1
    
    async def track_response_time(self, session_id: str, operation: str, func, *args, **kwargs):
        """Context manager to track function execution time"""
        timer_id = f"{session_id}_{operation}_{time.time()}"
        self.start_timer(timer_id)
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self.end_timer(timer_id, session_id, 'response_time', {'operation': operation})
            return result
        except Exception as e:
            self.end_timer(timer_id, session_id, 'error', {'operation': operation, 'error': str(e)})
            raise
    
    def track_compression_event(self, session_id: str, compression_data: Dict) -> None:
        """Track context compression events"""
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            session_id=session_id,
            metric_type='compression_event',
            value=compression_data.get('compression_ratio', 0),
            metadata={
                'original_tokens': compression_data.get('original_tokens', 0),
                'compressed_tokens': compression_data.get('compressed_tokens', 0),
                'compression_level': compression_data.get('compression_level', 'unknown'),
                'compression_time': compression_data.get('compression_time', 0)
            }
        )
        self.record_metric(metric)
    
    def track_token_usage(self, session_id: str, tokens_used: int, operation_type: str) -> None:
        """Track token usage for cost monitoring"""
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            session_id=session_id,
            metric_type='token_usage',
            value=float(tokens_used),
            metadata={'operation_type': operation_type}
        )
        self.record_metric(metric)
    
    def track_teaching_effectiveness(self, session_id: str, effectiveness_data: Dict) -> None:
        """Track teaching effectiveness metrics"""
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            session_id=session_id,
            metric_type='teaching_effectiveness',
            value=effectiveness_data.get('score', 0),
            metadata=effectiveness_data
        )
        self.record_metric(metric)
    
    def get_session_metrics(self, session_id: str) -> List[PerformanceMetric]:
        """Get all metrics for a specific session"""
        return self.metrics.get(session_id, [])
    
    def get_response_time_stats(self, session_id: str) -> Dict:
        """Get response time statistics for a session"""
        metrics = [m for m in self.get_session_metrics(session_id) if m.metric_type == 'response_time']
        
        if not metrics:
            return {'avg': 0, 'median': 0, 'min': 0, 'max': 0, 'count': 0}
        
        values = [m.value for m in metrics]
        return {
            'avg': mean(values),
            'median': median(values),
            'min': min(values),
            'max': max(values),
            'count': len(values)
        }
    
    async def generate_session_report(self, session_id: str) -> SessionPerformanceReport:
        """Generate comprehensive performance report for a session"""
        db = await get_database()
        session_doc = await db.sessions.find_one({"session_id": session_id})
        
        if not session_doc:
            raise ValueError(f"Session {session_id} not found")
        
        # Convert document to Session object
        session = Session(**session_doc)
        
        metrics = self.get_session_metrics(session_id)
        response_stats = self.get_response_time_stats(session_id)
        
        # Calculate compression metrics
        compression_metrics = [m for m in metrics if m.metric_type == 'compression_event']
        compression_savings = sum(m.value for m in compression_metrics) / len(compression_metrics) if compression_metrics else 0
        
        # Calculate token usage
        token_metrics = [m for m in metrics if m.metric_type == 'token_usage']
        total_tokens = sum(m.value for m in token_metrics)
        avg_tokens = total_tokens / len(token_metrics) if token_metrics else 0
        
        # Calculate effectiveness metrics
        effectiveness_metrics = [m for m in metrics if m.metric_type == 'teaching_effectiveness']
        effectiveness_scores = [m.metadata.get('student_engagement', 0) for m in effectiveness_metrics]
        avg_engagement = mean(effectiveness_scores) if effectiveness_scores else 0
        
        # Calculate session duration
        session_duration = (datetime.utcnow() - session.started_at).total_seconds()
        
        return SessionPerformanceReport(
            session_id=session_id,
            user_id=session.user_id,
            assignment_id=session.assignment_id,
            session_start=session.started_at,
            session_duration=session_duration,
            
            # Response time metrics
            avg_response_time=response_stats['avg'],
            median_response_time=response_stats['median'],
            min_response_time=response_stats['min'],
            max_response_time=response_stats['max'],
            
            # Intelligence metrics
            compression_events=len(compression_metrics),
            compression_savings=compression_savings,
            token_usage_total=int(total_tokens),
            token_usage_avg=avg_tokens,
            
            # Teaching effectiveness (mock values - would be calculated from actual session data)
            problem_completion_rate=0.85,
            hint_usage_rate=0.35,
            error_recovery_rate=0.75,
            student_engagement_score=avg_engagement,
            
            # System performance (mock values - would be from system monitoring)
            memory_usage_peak=256.0,
            cpu_usage_avg=45.0,
            api_errors_count=len([m for m in metrics if m.metric_type == 'error']),
            
            # AI model performance (mock values - would be from model evaluation)
            model_accuracy_score=0.92,
            prompt_effectiveness_score=0.88,
            adaptation_success_rate=0.79
        )
    
    def get_system_health_metrics(self) -> Dict:
        """Get overall system health metrics"""
        all_metrics = []
        for session_metrics in self.metrics.values():
            all_metrics.extend(session_metrics)
        
        if not all_metrics:
            return {'status': 'no_data', 'metrics': {}}
        
        response_times = [m.value for m in all_metrics if m.metric_type == 'response_time']
        errors = [m for m in all_metrics if m.metric_type == 'error']
        
        return {
            'status': 'healthy' if len(errors) < len(all_metrics) * 0.05 else 'degraded',
            'metrics': {
                'total_sessions': len(self.metrics),
                'total_requests': len(response_times),
                'avg_response_time': mean(response_times) if response_times else 0,
                'error_rate': len(errors) / len(all_metrics) if all_metrics else 0,
                'active_sessions': len([s for s in self.session_stats if self.session_stats[s]['total_requests'] > 0])
            }
        }
    
    def cleanup_old_metrics(self, hours: int = 24) -> None:
        """Clean up metrics older than specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        for session_id in list(self.metrics.keys()):
            self.metrics[session_id] = [
                m for m in self.metrics[session_id] 
                if m.timestamp > cutoff_time
            ]
            
            # Remove empty sessions
            if not self.metrics[session_id]:
                del self.metrics[session_id]
                if session_id in self.session_stats:
                    del self.session_stats[session_id]


# Global performance monitor instance
performance_monitor = PerformanceMonitor()