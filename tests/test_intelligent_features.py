"""
Comprehensive test suite for intelligent tutoring features.
Tests context compression, session analytics, performance monitoring, and caching.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from app.services.context_compression import context_compression_service, ContextData
from app.services.session_analytics import session_analytics_service, SessionAnalytics, UserLearningProfile
from app.services.performance_monitor import performance_monitor, PerformanceMetric, SessionPerformanceReport
from app.services.intelligent_cache import intelligent_cache, CacheLevel, IntelligentCacheDecorators
from app.services.resume_detection import resume_detection_service
from app.services.prompt_manager import prompt_manager

from app.models.session import Session, ConversationMessage
from app.models.enums import CompressionLevel, MessageType, ResumeType


class TestContextCompression:
    """Test context compression service"""
    
    @pytest.fixture
    def sample_messages(self):
        """Sample conversation messages for testing"""
        return [
            ConversationMessage(
                session_id="test_session",
                message_type=MessageType.USER,
                content="What is a variable in Python?",
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                tokens_used=8
            ),
            ConversationMessage(
                session_id="test_session",
                message_type=MessageType.ASSISTANT,
                content="A variable in Python is a name that refers to a value stored in memory...",
                timestamp=datetime.utcnow() - timedelta(minutes=29),
                tokens_used=45
            ),
            ConversationMessage(
                session_id="test_session",
                message_type=MessageType.USER,
                content="Can you give me an example?",
                timestamp=datetime.utcnow() - timedelta(minutes=28),
                tokens_used=7
            )
        ]
    
    @pytest.mark.asyncio
    async def test_token_estimation(self, sample_messages):
        """Test token estimation accuracy"""
        estimated = context_compression_service.estimate_tokens(sample_messages)
        expected = sum(msg.tokens_used or 0 for msg in sample_messages)
        
        # Should be close to actual count
        assert abs(estimated - expected) <= 10
    
    @pytest.mark.asyncio
    async def test_context_analysis(self, sample_messages):
        """Test context analysis for compression decision"""
        analysis = await context_compression_service.analyze_context_for_compression(
            "test_session", sample_messages
        )
        
        assert "learning_profile" in analysis
        assert "interaction_patterns" in analysis
        assert "compression_recommendation" in analysis
        assert analysis["total_tokens"] > 0
    
    @pytest.mark.asyncio
    async def test_three_tier_compression(self, sample_messages):
        """Test all three compression levels"""
        # Test full detail (no compression)
        result_full = await context_compression_service.compress_conversation(
            sample_messages, CompressionLevel.FULL_DETAIL
        )
        assert result_full.compression_level == CompressionLevel.FULL_DETAIL
        assert len(result_full.compressed_messages) == len(sample_messages)
        
        # Test summarized + recent
        with patch('app.services.context_compression.openai_client') as mock_openai:
            mock_openai.chat.completions.create.return_value = Mock(
                choices=[Mock(message=Mock(content="Summary of conversation about Python variables"))]
            )
            
            result_summary = await context_compression_service.compress_conversation(
                sample_messages, CompressionLevel.SUMMARIZED_PLUS_RECENT
            )
            assert result_summary.compression_level == CompressionLevel.SUMMARIZED_PLUS_RECENT
            assert result_summary.compression_ratio < 1.0
        
        # Test high-level summary
        with patch('app.services.context_compression.openai_client') as mock_openai:
            mock_openai.chat.completions.create.return_value = Mock(
                choices=[Mock(message=Mock(content=json.dumps({
                    "concepts_learned": ["variables", "basic_syntax"],
                    "competency_level": "beginner",
                    "learning_velocity": "moderate"
                })))]
            )
            
            result_high_level = await context_compression_service.compress_conversation(
                sample_messages, CompressionLevel.HIGH_LEVEL_SUMMARY
            )
            assert result_high_level.compression_level == CompressionLevel.HIGH_LEVEL_SUMMARY
            assert result_high_level.compression_ratio < 0.5
    
    @pytest.mark.asyncio
    async def test_adaptive_compression(self, sample_messages):
        """Test adaptive compression based on token count"""
        # Low token count - should stay full detail
        short_messages = sample_messages[:1]
        result = await context_compression_service.adaptive_compress_context(
            "test_session", short_messages
        )
        assert result.compression_level == CompressionLevel.FULL_DETAIL
        
        # High token count - should compress
        many_messages = sample_messages * 50  # Simulate long conversation
        with patch('app.services.context_compression.openai_client') as mock_openai:
            mock_openai.chat.completions.create.return_value = Mock(
                choices=[Mock(message=Mock(content="Compressed summary"))]
            )
            
            result = await context_compression_service.adaptive_compress_context(
                "test_session", many_messages
            )
            assert result.compression_level in [
                CompressionLevel.SUMMARIZED_PLUS_RECENT, 
                CompressionLevel.HIGH_LEVEL_SUMMARY
            ]


class TestSessionAnalytics:
    """Test session analytics service"""
    
    @pytest.fixture
    def sample_session(self):
        """Sample session for testing"""
        return Session(
            session_id="test_analytics_session",
            user_id="test_user",
            assignment_id="test_assignment",
            session_number=1,
            started_at=datetime.utcnow() - timedelta(hours=1),
            current_problem=1,
            status="active"
        )
    
    @pytest.mark.asyncio
    async def test_interaction_pattern_analysis(self, sample_session):
        """Test analysis of user interaction patterns"""
        messages = [
            ConversationMessage(
                session_id=sample_session.session_id,
                message_type=MessageType.USER,
                content="How do I create a function?",
                timestamp=datetime.utcnow(),
                metadata={"input_type": "question"}
            ),
            ConversationMessage(
                session_id=sample_session.session_id,
                message_type=MessageType.USER,
                content="def my_function():\n    pass",
                timestamp=datetime.utcnow(),
                metadata={"input_type": "code_submission"}
            )
        ]
        
        patterns = session_analytics_service._analyze_interaction_patterns(messages)
        
        assert patterns["question_frequency"] > 0
        assert patterns["code_pattern"] in ["minimal", "moderate", "frequent"]
        assert patterns["help_seeking"] in ["low", "medium", "high"]
        assert 0 <= patterns["engagement"] <= 1
    
    @pytest.mark.asyncio
    async def test_learning_pattern_identification(self, sample_session):
        """Test identification of learning patterns"""
        messages = [
            ConversationMessage(
                session_id=sample_session.session_id,
                message_type=MessageType.USER,
                content="What is a loop?",
                timestamp=datetime.utcnow()
            )
        ]
        
        interaction_patterns = {"question_frequency": 0.8, "code_pattern": "frequent", "help_seeking": "high"}
        patterns = session_analytics_service._identify_learning_patterns(messages, interaction_patterns)
        
        assert isinstance(patterns, list)
        for pattern in patterns:
            assert hasattr(pattern, 'pattern_type')
            assert hasattr(pattern, 'effectiveness_score')
            assert hasattr(pattern, 'recommendations')
    
    @pytest.mark.asyncio 
    async def test_session_analytics_generation(self, sample_session):
        """Test complete session analytics generation"""
        with patch('app.services.session_analytics.get_db_session') as mock_db:
            # Mock database queries
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.first.return_value = sample_session
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            
            with patch('app.services.performance_monitor.performance_monitor.generate_session_report') as mock_perf:
                mock_perf.return_value = SessionPerformanceReport(
                    session_id=sample_session.session_id,
                    user_id=sample_session.user_id,
                    assignment_id=sample_session.assignment_id,
                    session_start=sample_session.started_at,
                    session_duration=3600,
                    avg_response_time=1.2,
                    median_response_time=1.0,
                    min_response_time=0.5,
                    max_response_time=3.0,
                    compression_events=2,
                    compression_savings=0.65,
                    token_usage_total=450,
                    token_usage_avg=25,
                    problem_completion_rate=0.8,
                    hint_usage_rate=0.3,
                    error_recovery_rate=0.7,
                    student_engagement_score=0.85,
                    memory_usage_peak=128.0,
                    cpu_usage_avg=35.0,
                    api_errors_count=0,
                    model_accuracy_score=0.92,
                    prompt_effectiveness_score=0.88,
                    adaptation_success_rate=0.79
                )
                
                analytics = await session_analytics_service.analyze_session(sample_session.session_id)
                
                assert analytics.session_id == sample_session.session_id
                assert analytics.user_id == sample_session.user_id
                assert analytics.duration_minutes > 0
                assert isinstance(analytics.learning_patterns, list)
                assert isinstance(analytics.next_session_recommendations, list)


class TestPerformanceMonitor:
    """Test performance monitoring service"""
    
    def test_timer_functionality(self):
        """Test performance timer operations"""
        timer_id = "test_timer"
        session_id = "test_session"
        
        # Start timer
        performance_monitor.start_timer(timer_id)
        assert timer_id in performance_monitor.active_timers
        
        # End timer
        import time
        time.sleep(0.1)  # Small delay
        duration = performance_monitor.end_timer(timer_id, session_id, "test_operation")
        
        assert duration > 0
        assert timer_id not in performance_monitor.active_timers
        assert session_id in performance_monitor.metrics
    
    def test_metric_recording(self):
        """Test metric recording and retrieval"""
        session_id = "test_metrics_session"
        
        # Record various metrics
        performance_monitor.track_token_usage(session_id, 150, "generation")
        performance_monitor.track_compression_event(session_id, {
            "compression_ratio": 0.75,
            "original_tokens": 200,
            "compressed_tokens": 150,
            "compression_level": "medium"
        })
        
        # Retrieve metrics
        metrics = performance_monitor.get_session_metrics(session_id)
        assert len(metrics) >= 2
        
        # Check response time stats
        stats = performance_monitor.get_response_time_stats(session_id)
        assert "avg" in stats
        assert "median" in stats
        assert "count" in stats
    
    @pytest.mark.asyncio
    async def test_session_report_generation(self):
        """Test comprehensive session report generation"""
        session_id = "test_report_session"
        
        # Add some test metrics
        performance_monitor.track_token_usage(session_id, 100, "response")
        performance_monitor.track_compression_event(session_id, {
            "compression_ratio": 0.8,
            "original_tokens": 500,
            "compressed_tokens": 400
        })
        
        with patch('app.services.performance_monitor.get_db_session') as mock_db:
            mock_session = Mock()
            mock_session.session_id = session_id
            mock_session.user_id = "test_user"
            mock_session.assignment_id = "test_assignment"
            mock_session.started_at = datetime.utcnow() - timedelta(hours=1)
            
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.first.return_value = mock_session
            
            report = await performance_monitor.generate_session_report(session_id)
            
            assert report.session_id == session_id
            assert report.user_id == "test_user"
            assert report.session_duration > 0
            assert report.token_usage_total > 0
    
    def test_system_health_metrics(self):
        """Test system health monitoring"""
        # Add some test data
        performance_monitor.track_token_usage("session1", 100, "test")
        performance_monitor.track_token_usage("session2", 150, "test")
        
        health = performance_monitor.get_system_health_metrics()
        
        assert "status" in health
        assert "metrics" in health
        assert health["status"] in ["healthy", "degraded", "no_data"]


class TestIntelligentCache:
    """Test intelligent caching system"""
    
    @pytest.mark.asyncio
    async def test_basic_cache_operations(self):
        """Test basic cache set/get operations"""
        key = "test_key"
        data = {"message": "test data", "timestamp": datetime.utcnow().isoformat()}
        
        # Set data
        success = await intelligent_cache.set(key, data, ttl=300)
        assert success
        
        # Get data
        retrieved = await intelligent_cache.get(key)
        assert retrieved is not None
        assert retrieved["message"] == data["message"]
    
    @pytest.mark.asyncio
    async def test_cache_levels(self):
        """Test different cache levels"""
        # L1 Memory cache
        await intelligent_cache.set("l1_key", "l1_data", level=CacheLevel.L1_MEMORY)
        l1_data = await intelligent_cache.get("l1_key", CacheLevel.L1_MEMORY)
        assert l1_data == "l1_data"
        
        # L2 Session cache
        session_key = "session:test_session:data"
        await intelligent_cache.set(session_key, "session_data", level=CacheLevel.L2_SESSION)
        session_data = await intelligent_cache.get(session_key, CacheLevel.L2_SESSION)
        assert session_data == "session_data"
        
        # L3 User cache
        user_key = "user:test_user:profile"
        await intelligent_cache.set(user_key, "user_data", level=CacheLevel.L3_USER)
        user_data = await intelligent_cache.get(user_key, CacheLevel.L3_USER)
        assert user_data == "user_data"
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache TTL and expiration"""
        key = "expiring_key"
        data = "expiring_data"
        
        # Set with very short TTL
        await intelligent_cache.set(key, data, ttl=1)
        
        # Should be available immediately
        retrieved = await intelligent_cache.get(key)
        assert retrieved == data
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Should be None after expiration
        expired = await intelligent_cache.get(key)
        assert expired is None
    
    @pytest.mark.asyncio
    async def test_tag_based_invalidation(self):
        """Test cache invalidation by tags"""
        # Set multiple entries with same tag
        await intelligent_cache.set("key1", "data1", tags=["tag1", "common"])
        await intelligent_cache.set("key2", "data2", tags=["tag2", "common"])
        await intelligent_cache.set("key3", "data3", tags=["tag3"])
        
        # Verify all are cached
        assert await intelligent_cache.get("key1") == "data1"
        assert await intelligent_cache.get("key2") == "data2"
        assert await intelligent_cache.get("key3") == "data3"
        
        # Invalidate by common tag
        removed = await intelligent_cache.invalidate_by_tags(["common"])
        assert removed == 2
        
        # Check invalidation results
        assert await intelligent_cache.get("key1") is None
        assert await intelligent_cache.get("key2") is None
        assert await intelligent_cache.get("key3") == "data3"  # Should still exist
    
    @pytest.mark.asyncio
    async def test_data_compression(self):
        """Test automatic data compression for large entries"""
        # Large data that should trigger compression
        large_data = {"content": "x" * 2000, "metadata": {"size": "large"}}
        
        # Set large data
        await intelligent_cache.set("large_key", large_data)
        
        # Retrieve and verify
        retrieved = await intelligent_cache.get("large_key")
        assert retrieved["content"] == large_data["content"]
        assert retrieved["metadata"]["size"] == "large"
    
    def test_cache_statistics(self):
        """Test cache statistics generation"""
        stats = intelligent_cache.get_cache_stats()
        
        assert hasattr(stats, 'total_entries')
        assert hasattr(stats, 'hit_rate')
        assert hasattr(stats, 'miss_rate')
        assert hasattr(stats, 'memory_usage_mb')
        assert 0 <= stats.hit_rate <= 1
        assert 0 <= stats.miss_rate <= 1
    
    @pytest.mark.asyncio
    async def test_cache_decorators(self):
        """Test cache decorators for intelligent features"""
        decorators = IntelligentCacheDecorators(intelligent_cache)
        
        @decorators.session_cache(ttl=300)
        async def test_session_function(session_id: str, data: str):
            return f"processed_{data}_for_{session_id}"
        
        # First call should execute function
        result1 = await test_session_function("session123", "test_data")
        assert result1 == "processed_test_data_for_session123"
        
        # Second call should use cache
        result2 = await test_session_function("session123", "test_data")
        assert result2 == result1
        
        @decorators.user_cache(ttl=600)
        async def test_user_function(user_id: str, profile_data: dict):
            return {"user": user_id, "processed": profile_data}
        
        # Test user cache decorator
        profile = {"name": "Test User", "level": "beginner"}
        result = await test_user_function("user456", profile)
        assert result["user"] == "user456"
        assert result["processed"] == profile


class TestResumeDetection:
    """Test resume detection service"""
    
    @pytest.mark.asyncio
    async def test_resume_type_detection(self):
        """Test different resume type detection scenarios"""
        session_id = "test_resume_session"
        user_id = "test_user"
        assignment_id = "test_assignment"
        
        with patch('app.services.resume_detection.get_db_session') as mock_db:
            # Mock no previous sessions (fresh start)
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            
            resume_type = await resume_detection_service.detect_resume_type(
                user_id, assignment_id
            )
            assert resume_type == ResumeType.FRESH_START
            
            # Mock recent incomplete session (mid conversation)
            mock_recent_session = Mock()
            mock_recent_session.session_id = "previous_session"
            mock_recent_session.updated_at = datetime.utcnow() - timedelta(minutes=30)
            mock_recent_session.status = "paused"
            mock_recent_session.current_problem = 2
            
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_recent_session]
            
            resume_type = await resume_detection_service.detect_resume_type(
                user_id, assignment_id
            )
            assert resume_type == ResumeType.MID_CONVERSATION


class TestPromptManager:
    """Test prompt manager service"""
    
    def test_prompt_template_selection(self):
        """Test prompt template selection based on scenario"""
        # Test different scenarios
        scenarios = [
            "initial_greeting",
            "concept_explanation", 
            "debugging_help",
            "code_review",
            "encouragement"
        ]
        
        for scenario in scenarios:
            template = prompt_manager.get_prompt_template(scenario)
            assert template is not None
            assert "system_prompt" in template
            assert "user_prompt_template" in template
    
    @pytest.mark.asyncio
    async def test_context_aware_prompt_generation(self):
        """Test context-aware prompt generation"""
        context = {
            "student_level": "beginner",
            "current_topic": "variables",
            "previous_struggles": ["syntax_errors"],
            "learning_style": "visual"
        }
        
        prompt = await prompt_manager.generate_context_aware_prompt(
            "concept_explanation", context
        )
        
        assert prompt is not None
        assert len(prompt) > 0
        # Should contain context-specific adaptations
        assert any(keyword in prompt.lower() for keyword in ["beginner", "variable", "visual"])


class TestIntegration:
    """Integration tests for intelligent tutoring features"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_intelligent_session(self):
        """Test complete intelligent session workflow"""
        session_id = "integration_test_session"
        user_id = "integration_test_user"
        assignment_id = "integration_test_assignment"
        
        # 1. Start with resume detection
        with patch('app.services.resume_detection.get_db_session') as mock_db:
            mock_db.return_value.__aenter__.return_value.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
            
            resume_type = await resume_detection_service.detect_resume_type(user_id, assignment_id)
            assert resume_type == ResumeType.FRESH_START
        
        # 2. Generate initial problem presentation
        problem_data = {
            "id": 1,
            "title": "Variables and Data Types",
            "description": "Learn about Python variables",
            "difficulty": "beginner"
        }
        
        presentation = await problem_presenter.present_problem(
            problem_data, {"student_level": "beginner"}
        )
        assert presentation is not None
        assert "problem_presentation" in presentation
        
        # 3. Simulate message exchange with caching
        messages = [
            ConversationMessage(
                session_id=session_id,
                message_type=MessageType.USER,
                content="What is a variable?",
                timestamp=datetime.utcnow()
            )
        ]
        
        # Cache the conversation context
        cache_key = f"session:{session_id}:context"
        await intelligent_cache.set(
            cache_key, messages, ttl=1800, 
            level=CacheLevel.L2_SESSION,
            tags=[f"session:{session_id}"]
        )
        
        # 4. Track performance metrics
        performance_monitor.start_timer("response_generation")
        # Simulate response generation time
        import time
        time.sleep(0.01)
        response_time = performance_monitor.end_timer(
            "response_generation", session_id, "ai_response"
        )
        assert response_time > 0
        
        # 5. Test context compression when needed
        if len(messages) > 10:  # Would trigger compression in real scenario
            with patch('app.services.context_compression.openai_client') as mock_openai:
                mock_openai.chat.completions.create.return_value = Mock(
                    choices=[Mock(message=Mock(content="Compressed context"))]
                )
                
                compressed = await context_compression_service.adaptive_compress_context(
                    session_id, messages
                )
                assert compressed.compression_level in CompressionLevel
        
        # 6. Verify cache functionality
        cached_context = await intelligent_cache.get(cache_key, CacheLevel.L2_SESSION)
        assert cached_context is not None
        assert len(cached_context) == len(messages)
        
        # 7. Clean up session cache
        removed_count = await intelligent_cache.invalidate_session(session_id)
        assert removed_count >= 0


# Fixture cleanup
@pytest.fixture(autouse=True)
async def cleanup_after_tests():
    """Clean up cache and monitoring data after each test"""
    yield
    
    # Clear caches
    await intelligent_cache.clear_all()
    
    # Clear analytics cache
    session_analytics_service.clear_cache()
    
    # Clear performance monitoring data
    performance_monitor.cleanup_old_metrics(hours=0)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])