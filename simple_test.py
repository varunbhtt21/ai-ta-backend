#!/usr/bin/env python3
"""
Simple test script to check if structured tutoring is calling OpenAI
"""

import asyncio
import httpx
import os

async def test_structured_api():
    """Simple test without authentication"""
    
    print("🧪 SIMPLE STRUCTURED API TEST")
    print("=" * 40)
    
    # Test 1: Check if backend is running
    print("\n📡 Test 1: Checking if backend is running...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("✅ Backend is running!")
                print(f"📋 Health check: {response.json()}")
            else:
                print(f"❌ Backend health check failed: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ Cannot connect to backend: {e}")
            return
    
    # Test 2: Check environment variables
    print("\n🔧 Test 2: Checking environment configuration...")
    
    # Check if we can access the backend environment
    try:
        from app.core.config import settings
        print(f"✅ App name: {settings.APP_NAME}")
        print(f"✅ Environment: {settings.ENVIRONMENT}")
        
        # Check OpenAI configuration (don't print the actual key!)
        if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
            print(f"✅ OpenAI API key is configured (length: {len(settings.OPENAI_API_KEY)})")
        else:
            print("❌ OpenAI API key is NOT configured!")
            
        if hasattr(settings, 'OPENAI_MODEL'):
            print(f"✅ OpenAI model: {settings.OPENAI_MODEL}")
        else:
            print("❌ OpenAI model not configured")
            
    except Exception as e:
        print(f"❌ Error checking configuration: {e}")
    
    # Test 3: Test OpenAI client directly
    print("\n🤖 Test 3: Testing OpenAI client directly...")
    try:
        from app.services.openai_client import openai_client
        from app.models import ConversationMessage, MessageType
        from datetime import datetime
        
        # Create a test message
        test_message = ConversationMessage(
            timestamp=datetime.utcnow(),
            message_type=MessageType.USER,
            content="Hello, I want to test if OpenAI is working"
        )
        
        # Test OpenAI call
        response = await openai_client.generate_response(
            messages=[test_message],
            system_prompt="You are a helpful AI tutor. Respond with 'OpenAI is working correctly!' to confirm the connection.",
            max_tokens=50,
            temperature=0.3
        )
        
        if response and response.get("success"):
            print("✅ OpenAI client is working!")
            print(f"📝 OpenAI Response: {response.get('content', 'No content')}")
        else:
            print("❌ OpenAI client failed!")
            print(f"📄 Response: {response}")
            
    except Exception as e:
        print(f"❌ Error testing OpenAI client: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Test structured tutoring engine directly
    print("\n🎯 Test 4: Testing structured tutoring engine...")
    try:
        from app.services.structured_tutoring_engine import StructuredTutoringEngine, StudentState
        from app.models import Assignment, Problem, ConversationMessage, MessageType
        from datetime import datetime
        
        # Create test data
        engine = StructuredTutoringEngine()
        
        test_problem = Problem(
            number=1,
            title="Test Problem",
            description="Write a simple hello world program",
            difficulty="easy",
            concepts=["basic programming"],
            starter_code="",
            solution_template="",
            test_cases=[],
            hints=[]
        )
        
        from bson import ObjectId
        
        test_assignment = Assignment(
            id=ObjectId(),
            title="Test Assignment", 
            description="Test assignment for debugging",
            problems=[test_problem],
            total_problems=1,
            course_id=ObjectId(),
            instructor_id=ObjectId(),
            curriculum_content="Basic programming concepts"
        )
        
        # Test the engine
        response = await engine.generate_structured_response(
            user_input="I want to start the problem",
            user_id="test_user",
            assignment=test_assignment,
            current_problem=test_problem,
            conversation_history=[],
            current_state=StudentState.INITIAL_GREETING,
            problem_context={
                "title": "Test Problem",
                "description": "Write a simple hello world program",
                "concepts": ["basic programming"],
                "difficulty": "easy"
            }
        )
        
        print("✅ Structured tutoring engine is working!")
        print(f"📝 Engine Response: {response.response_text}")
        print(f"📊 Student State: {response.student_state}")
        print(f"🎯 Tutoring Mode: {response.tutoring_mode}")
        
        # Check if response is hardcoded
        hardcoded_indicators = [
            "Can you think about what the problem is asking",
            "What will you use to store the numbers",
            "What do you think you need to do"
        ]
        
        is_hardcoded = any(indicator in response.response_text for indicator in hardcoded_indicators)
        if is_hardcoded:
            print("⚠️  WARNING: Response appears to be hardcoded!")
        else:
            print("✅ Response appears to be dynamically generated")
            
    except Exception as e:
        print(f"❌ Error testing structured tutoring engine: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Make sure we're in the right directory
    os.chdir("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
    
    try:
        asyncio.run(test_structured_api())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()