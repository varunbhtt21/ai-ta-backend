#!/usr/bin/env python3
"""
Debug script to specifically test the problem statement request issue
"""

import asyncio
import os

async def debug_problem_statement():
    """Test specifically the problem statement request scenario"""
    
    print("🔍 DEBUGGING PROBLEM STATEMENT REQUESTS")
    print("=" * 50)
    
    try:
        from app.services.structured_tutoring_engine import StructuredTutoringEngine, StudentState
        from app.models import Assignment, Problem, ConversationMessage, MessageType
        from bson import ObjectId
        from datetime import datetime
        
        # Create test data similar to your actual problem
        engine = StructuredTutoringEngine()
        
        test_problem = Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.\n\nSample Input:\nEnter number 1: 3\nEnter number 2: 7\nEnter number 3: 2\nEnter number 4: 9\nEnter number 5: 5\n\nSample Output:\n[3, 7, 2, 9, 5]",
            difficulty="easy",
            concepts=["lists", "loops", "input"],
            starter_code="",
            solution_template="",
            test_cases=[],
            hints=[]
        )
        
        test_assignment = Assignment(
            id=ObjectId(),
            title="Python Basics Assignment", 
            description="Learn basic Python programming concepts",
            problems=[test_problem],
            total_problems=1,
            course_id=ObjectId(),
            instructor_id=ObjectId(),
            curriculum_content="Basic Python programming including lists, loops, and user input"
        )
        
        # Test scenarios that should trigger different responses
        test_scenarios = [
            {
                "input": "I'm ready to start!",
                "expected": "Should present problem statement",
                "context": None
            },
            {
                "input": "give me the problem statement?",
                "expected": "Should show actual problem description",
                "context": {
                    "title": "Create a List with User Input",
                    "description": "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
                    "concepts": ["lists", "loops", "input"],
                    "difficulty": "easy"
                }
            },
            {
                "input": "explain the problem statement?",
                "expected": "Should show actual problem description",
                "context": {
                    "title": "Create a List with User Input", 
                    "description": "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
                    "concepts": ["lists", "loops", "input"],
                    "difficulty": "easy"
                }
            },
            {
                "input": "what am i supposed to do?",
                "expected": "Should show actual problem description",
                "context": {
                    "title": "Create a List with User Input",
                    "description": "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
                    "concepts": ["lists", "loops", "input"],
                    "difficulty": "easy"
                }
            }
        ]
        
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n🧪 Test Scenario {i}: {scenario['expected']}")
            print(f"📤 Input: '{scenario['input']}'")
            
            try:
                # Test the engine with the specific input
                response = await engine.generate_structured_response(
                    user_input=scenario["input"],
                    user_id="test_user",
                    assignment=test_assignment,
                    current_problem=test_problem,
                    conversation_history=[],
                    current_state=StudentState.INITIAL_GREETING,
                    problem_context=scenario["context"]
                )
                
                print(f"✅ Response Generated!")
                print(f"📝 AI Response: '{response.response_text}'")
                print(f"📊 Student State: {response.student_state}")
                print(f"🎯 Tutoring Mode: {response.tutoring_mode}")
                print(f"📋 Teaching Notes: {response.teaching_notes}")
                
                # Check if response contains actual problem details
                if scenario["context"] and "description" in scenario["context"]:
                    expected_content = scenario["context"]["description"]
                    if expected_content in response.response_text:
                        print("✅ Response contains actual problem description!")
                    else:
                        print("❌ Response does NOT contain actual problem description!")
                        print(f"🔍 Expected to find: '{expected_content[:50]}...'")
                
                # Check for hardcoded patterns
                hardcoded_patterns = [
                    "What will you use to store the numbers that the user inputs?",
                    "What do you think you need to do with the numbers after the user enters them?",
                    "Can you think about what the problem is asking you to do step by step?"
                ]
                
                is_hardcoded = any(pattern in response.response_text for pattern in hardcoded_patterns)
                if is_hardcoded:
                    print("⚠️  WARNING: This appears to be a hardcoded response!")
                    print("🔍 Found hardcoded pattern in response")
                else:
                    print("✅ Response appears to be dynamically generated")
                
            except Exception as e:
                print(f"❌ Error in scenario {i}: {e}")
                import traceback
                traceback.print_exc()
            
            print("-" * 50)
    
    except Exception as e:
        print(f"❌ Error setting up test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Make sure we're in the right directory
    os.chdir("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
    
    try:
        asyncio.run(debug_problem_statement())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()