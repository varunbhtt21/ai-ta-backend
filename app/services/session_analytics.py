"""
Advanced session analytics service for intelligent tutoring system.
Provides insights into learning patterns, performance trends, and teaching effectiveness.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging
from statistics import mean, median, stdev

from ..models.session import Session, ConversationMessage
from ..models.enums import SessionStatus, MessageType, ResumeType
from ..database.connection import get_database
from .performance_monitor import performance_monitor, SessionPerformanceReport

logger = logging.getLogger(__name__)


@dataclass
class LearningPattern:
    """Individual learning pattern analysis"""
    pattern_type: str
    frequency: int
    effectiveness_score: float
    description: str
    recommendations: List[str]


@dataclass
class SessionAnalytics:
    """Comprehensive session analytics data"""
    session_id: str
    user_id: str
    assignment_id: str
    session_number: int
    
    # Basic metrics
    duration_minutes: float
    messages_count: int
    problems_attempted: int
    problems_completed: int
    
    # Learning progression
    learning_velocity: str
    competency_growth: float
    concept_mastery: Dict[str, float]
    difficulty_progression: List[str]
    
    # Interaction patterns
    question_asking_frequency: float
    help_seeking_behavior: str
    code_submission_pattern: str
    response_engagement_level: float
    
    # Teaching effectiveness
    ai_response_quality: float
    teaching_strategy_effectiveness: float
    personalization_success_rate: float
    adaptive_content_impact: float
    
    # Performance insights
    peak_performance_time: Optional[str]
    struggle_points: List[Dict[str, Any]]
    breakthrough_moments: List[Dict[str, Any]]
    learning_patterns: List[LearningPattern]
    
    # Recommendations
    next_session_recommendations: List[str]
    teaching_strategy_suggestions: List[str]
    content_adaptation_suggestions: List[str]


@dataclass
class UserLearningProfile:
    """Comprehensive user learning profile across sessions"""
    user_id: str
    total_sessions: int
    total_study_time: float
    
    # Learning characteristics
    preferred_learning_style: str
    optimal_session_duration: float
    best_performance_time: str
    learning_velocity: str
    
    # Competency tracking
    overall_competency: Dict[str, float]
    competency_growth_rate: float
    strengths: List[str]
    improvement_areas: List[str]
    
    # Engagement patterns
    engagement_trend: str
    motivation_indicators: Dict[str, float]
    help_seeking_patterns: Dict[str, int]
    
    # Performance trends
    performance_consistency: float
    problem_solving_efficiency: float
    knowledge_retention_rate: float
    
    # Predictive insights
    success_probability: float
    risk_factors: List[str]
    recommended_interventions: List[str]


class SessionAnalyticsService:
    """
    Advanced analytics service for intelligent tutoring sessions.
    Analyzes learning patterns, performance trends, and teaching effectiveness.
    """
    
    def __init__(self):
        self.analytics_cache: Dict[str, SessionAnalytics] = {}
        self.user_profiles_cache: Dict[str, UserLearningProfile] = {}
    
    async def analyze_session(self, session_id: str) -> SessionAnalytics:
        """Generate comprehensive analytics for a session"""
        if session_id in self.analytics_cache:
            return self.analytics_cache[session_id]
        
        db = await get_database()
        session_doc = await db.sessions.find_one({"session_id": session_id})
        if not session_doc:
            raise ValueError(f"Session {session_id} not found")
        
        # Convert document to Session object (simplified)
        session = Session(**session_doc)
        
        messages_cursor = db.conversations.find(
            {"session_id": session_id}
        ).sort("timestamp", 1)
        
        messages = []
        async for msg_doc in messages_cursor:
            messages.append(ConversationMessage(**msg_doc))
        
        # Get performance report
        perf_report = await performance_monitor.generate_session_report(session_id)
        
        # Analyze interaction patterns
        interaction_patterns = self._analyze_interaction_patterns(messages)
        
        # Analyze learning progression
        learning_progression = self._analyze_learning_progression(session, messages)
        
        # Analyze teaching effectiveness
        teaching_effectiveness = self._analyze_teaching_effectiveness(messages, perf_report)
        
        # Identify learning patterns
        learning_patterns = self._identify_learning_patterns(messages, interaction_patterns)
        
        # Generate insights and recommendations
        insights = self._generate_session_insights(session, messages, learning_patterns)
        
        analytics = SessionAnalytics(
            session_id=session_id,
            user_id=session.user_id,
            assignment_id=session.assignment_id,
            session_number=session.session_number,
            
            # Basic metrics
            duration_minutes=(datetime.utcnow() - session.started_at).total_seconds() / 60,
            messages_count=len(messages),
            problems_attempted=interaction_patterns['problems_attempted'],
            problems_completed=interaction_patterns['problems_completed'],
            
            # Learning progression
            learning_velocity=learning_progression['velocity'],
            competency_growth=learning_progression['growth'],
            concept_mastery=learning_progression['mastery'],
            difficulty_progression=learning_progression['difficulty_progression'],
            
            # Interaction patterns
            question_asking_frequency=interaction_patterns['question_frequency'],
            help_seeking_behavior=interaction_patterns['help_seeking'],
            code_submission_pattern=interaction_patterns['code_pattern'],
            response_engagement_level=interaction_patterns['engagement'],
            
            # Teaching effectiveness
            ai_response_quality=teaching_effectiveness['response_quality'],
            teaching_strategy_effectiveness=teaching_effectiveness['strategy_effectiveness'],
            personalization_success_rate=teaching_effectiveness['personalization_success'],
            adaptive_content_impact=teaching_effectiveness['adaptive_impact'],
            
            # Performance insights
            peak_performance_time=insights['peak_time'],
            struggle_points=insights['struggles'],
            breakthrough_moments=insights['breakthroughs'],
            learning_patterns=learning_patterns,
            
            # Recommendations
            next_session_recommendations=insights['next_session_recommendations'],
            teaching_strategy_suggestions=insights['teaching_suggestions'],
            content_adaptation_suggestions=insights['content_suggestions']
        )
        
        self.analytics_cache[session_id] = analytics
        return analytics
    
    def _analyze_interaction_patterns(self, messages: List[ConversationMessage]) -> Dict[str, Any]:
        """Analyze user interaction patterns from conversation messages"""
        user_messages = [m for m in messages if m.message_type == MessageType.USER]
        ai_messages = [m for m in messages if m.message_type == MessageType.ASSISTANT]
        
        if not user_messages:
            return {
                'problems_attempted': 0,
                'problems_completed': 0,
                'question_frequency': 0.0,
                'help_seeking': 'low',
                'code_pattern': 'minimal',
                'engagement': 0.0
            }
        
        # Analyze message types
        questions = len([m for m in user_messages if '?' in m.content or 'how' in m.content.lower() or 'what' in m.content.lower()])
        code_submissions = len([m for m in user_messages if m.metadata and m.metadata.get('input_type') == 'code_submission'])
        help_requests = len([m for m in user_messages if 'help' in m.content.lower() or 'stuck' in m.content.lower()])
        
        # Calculate patterns
        question_frequency = questions / len(user_messages) if user_messages else 0
        help_seeking = 'high' if help_requests > len(user_messages) * 0.3 else 'medium' if help_requests > len(user_messages) * 0.1 else 'low'
        code_pattern = 'frequent' if code_submissions > 5 else 'moderate' if code_submissions > 2 else 'minimal'
        
        # Engagement calculation (based on message length and frequency)
        avg_message_length = mean([len(m.content) for m in user_messages]) if user_messages else 0
        engagement = min(1.0, (avg_message_length / 100) * (len(user_messages) / 10))
        
        return {
            'problems_attempted': len(set([m.metadata.get('problem_number', 1) for m in user_messages if m.metadata])),
            'problems_completed': code_submissions,  # Approximation
            'question_frequency': question_frequency,
            'help_seeking': help_seeking,
            'code_pattern': code_pattern,
            'engagement': engagement
        }
    
    def _analyze_learning_progression(self, session: Session, messages: List[ConversationMessage]) -> Dict[str, Any]:
        """Analyze learning progression throughout the session"""
        # Mock implementation - would analyze actual problem-solving progression
        return {
            'velocity': 'moderate',
            'growth': 0.65,
            'mastery': {
                'variables': 0.8,
                'functions': 0.6,
                'loops': 0.7,
                'conditionals': 0.9
            },
            'difficulty_progression': ['easy', 'medium', 'medium', 'hard']
        }
    
    def _analyze_teaching_effectiveness(self, messages: List[ConversationMessage], perf_report: SessionPerformanceReport) -> Dict[str, float]:
        """Analyze the effectiveness of AI teaching strategies"""
        ai_messages = [m for m in messages if m.message_type == MessageType.ASSISTANT]
        
        # Calculate response quality (based on message metadata)
        enhanced_responses = [m for m in ai_messages if m.metadata and m.metadata.get('enhanced')]
        response_quality = len(enhanced_responses) / len(ai_messages) if ai_messages else 0
        
        # Strategy effectiveness (based on student engagement after AI responses)
        strategy_effectiveness = perf_report.student_engagement_score
        
        # Personalization success (mock calculation)
        personalization_success = 0.85
        
        # Adaptive content impact (mock calculation)
        adaptive_impact = 0.78
        
        return {
            'response_quality': response_quality,
            'strategy_effectiveness': strategy_effectiveness,
            'personalization_success': personalization_success,
            'adaptive_impact': adaptive_impact
        }
    
    def _identify_learning_patterns(self, messages: List[ConversationMessage], interaction_patterns: Dict) -> List[LearningPattern]:
        """Identify specific learning patterns from session data"""
        patterns = []
        
        # Pattern 1: Question-driven learning
        if interaction_patterns['question_frequency'] > 0.4:
            patterns.append(LearningPattern(
                pattern_type='question_driven',
                frequency=int(interaction_patterns['question_frequency'] * 10),
                effectiveness_score=0.85,
                description='Student learns primarily by asking questions',
                recommendations=['Provide more guided questions', 'Encourage deeper inquiry']
            ))
        
        # Pattern 2: Trial-and-error approach
        if interaction_patterns['code_pattern'] == 'frequent':
            patterns.append(LearningPattern(
                pattern_type='trial_and_error',
                frequency=5,
                effectiveness_score=0.70,
                description='Student learns through experimentation',
                recommendations=['Provide immediate feedback', 'Guide systematic testing']
            ))
        
        # Pattern 3: Help-seeking behavior
        if interaction_patterns['help_seeking'] == 'high':
            patterns.append(LearningPattern(
                pattern_type='help_seeking',
                frequency=7,
                effectiveness_score=0.60,
                description='Student frequently seeks assistance',
                recommendations=['Build confidence gradually', 'Provide scaffolded support']
            ))
        
        return patterns
    
    def _generate_session_insights(self, session: Session, messages: List[ConversationMessage], patterns: List[LearningPattern]) -> Dict[str, Any]:
        """Generate actionable insights from session analysis"""
        # Mock implementation - would analyze actual session data for insights
        return {
            'peak_time': '15:30-16:00',
            'struggles': [
                {'topic': 'loops', 'difficulty_level': 0.8, 'duration_minutes': 12},
                {'topic': 'function_parameters', 'difficulty_level': 0.6, 'duration_minutes': 8}
            ],
            'breakthroughs': [
                {'topic': 'variable_scope', 'understanding_jump': 0.4, 'timestamp': '15:45'}
            ],
            'next_session_recommendations': [
                'Review loop concepts with additional examples',
                'Practice function parameter passing',
                'Introduce debugging techniques'
            ],
            'teaching_suggestions': [
                'Use more visual explanations for loops',
                'Provide step-by-step function examples',
                'Increase encouragement and positive reinforcement'
            ],
            'content_suggestions': [
                'Add interactive loop visualization',
                'Include more beginner-friendly function exercises',
                'Provide concept review before new topics'
            ]
        }
    
    async def generate_user_learning_profile(self, user_id: str) -> UserLearningProfile:
        """Generate comprehensive learning profile for a user across all sessions"""
        if user_id in self.user_profiles_cache:
            return self.user_profiles_cache[user_id]
        
        db = await get_database()
        sessions_cursor = db.sessions.find({"user_id": user_id})
        sessions = []
        async for session_doc in sessions_cursor:
            sessions.append(Session(**session_doc))
        
        if not sessions:
            raise ValueError(f"No sessions found for user {user_id}")
        
        # Analyze all sessions for the user
        session_analytics = []
        for session in sessions:
            try:
                analytics = await self.analyze_session(session.session_id)
                session_analytics.append(analytics)
            except Exception as e:
                logger.warning(f"Failed to analyze session {session.session_id}: {e}")
        
        if not session_analytics:
            raise ValueError(f"No valid session analytics for user {user_id}")
        
        # Aggregate learning profile data
        profile = self._aggregate_user_profile(user_id, session_analytics)
        
        self.user_profiles_cache[user_id] = profile
        return profile
    
    def _aggregate_user_profile(self, user_id: str, session_analytics: List[SessionAnalytics]) -> UserLearningProfile:
        """Aggregate session analytics into comprehensive user profile"""
        total_sessions = len(session_analytics)
        total_study_time = sum(a.duration_minutes for a in session_analytics)
        
        # Determine preferred learning style
        learning_styles = [pattern.pattern_type for analytics in session_analytics for pattern in analytics.learning_patterns]
        preferred_style = max(set(learning_styles), key=learning_styles.count) if learning_styles else 'balanced'
        
        # Calculate competency aggregation
        all_competencies = {}
        for analytics in session_analytics:
            for concept, mastery in analytics.concept_mastery.items():
                if concept not in all_competencies:
                    all_competencies[concept] = []
                all_competencies[concept].append(mastery)
        
        overall_competency = {
            concept: mean(scores) for concept, scores in all_competencies.items()
        }
        
        # Calculate growth rate
        if len(session_analytics) > 1:
            recent_competency = mean(session_analytics[-1].concept_mastery.values())
            initial_competency = mean(session_analytics[0].concept_mastery.values())
            growth_rate = (recent_competency - initial_competency) / len(session_analytics)
        else:
            growth_rate = 0.0
        
        # Identify strengths and improvement areas
        competency_items = list(overall_competency.items())
        competency_items.sort(key=lambda x: x[1], reverse=True)
        strengths = [item[0] for item in competency_items[:3]]
        improvement_areas = [item[0] for item in competency_items[-3:]]
        
        return UserLearningProfile(
            user_id=user_id,
            total_sessions=total_sessions,
            total_study_time=total_study_time,
            
            # Learning characteristics
            preferred_learning_style=preferred_style,
            optimal_session_duration=mean([a.duration_minutes for a in session_analytics]),
            best_performance_time='15:00-17:00',  # Mock - would be calculated from actual data
            learning_velocity='moderate',
            
            # Competency tracking
            overall_competency=overall_competency,
            competency_growth_rate=growth_rate,
            strengths=strengths,
            improvement_areas=improvement_areas,
            
            # Engagement patterns
            engagement_trend='stable',
            motivation_indicators={'curiosity': 0.8, 'persistence': 0.7, 'confidence': 0.6},
            help_seeking_patterns={'questions': 15, 'hints': 8, 'examples': 12},
            
            # Performance trends
            performance_consistency=0.75,
            problem_solving_efficiency=0.68,
            knowledge_retention_rate=0.82,
            
            # Predictive insights
            success_probability=0.85,
            risk_factors=['attention_span', 'concept_retention'],
            recommended_interventions=[
                'Shorter, more frequent sessions',
                'Spaced repetition for weak concepts',
                'Gamification elements for motivation'
            ]
        )
    
    async def get_teaching_strategy_recommendations(self, session_id: str) -> Dict[str, Any]:
        """Get AI teaching strategy recommendations based on session analysis"""
        analytics = await self.analyze_session(session_id)
        
        recommendations = {
            'primary_strategy': 'adaptive_scaffolding',
            'focus_areas': analytics.learning_patterns,
            'adjustments': [],
            'next_steps': analytics.next_session_recommendations
        }
        
        # Adjust strategy based on learning patterns
        for pattern in analytics.learning_patterns:
            if pattern.pattern_type == 'question_driven':
                recommendations['adjustments'].append('Increase Socratic questioning')
            elif pattern.pattern_type == 'trial_and_error':
                recommendations['adjustments'].append('Provide guided exploration opportunities')
            elif pattern.pattern_type == 'help_seeking':
                recommendations['adjustments'].append('Gradually reduce scaffolding')
        
        return recommendations
    
    def clear_cache(self):
        """Clear analytics cache"""
        self.analytics_cache.clear()
        self.user_profiles_cache.clear()


# Global analytics service instance
session_analytics_service = SessionAnalyticsService()