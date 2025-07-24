#!/usr/bin/env python3
"""
Debug OpenAI calls in the structured tutoring engine to find why they're failing
"""

import asyncio
import os
import logging

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)

async def debug_openai_calls():
    """Debug the specific OpenAI calls in _guide_with_questions"""
    
    print("🔍 DEBUGGING OPENAI CALLS IN STRUCTURED TUTORING")
    print("=" * 60)
    
    try:
        from app.services.structured_tutoring_engine import StructuredTutoringEngine
        from app.models import Problem
        
        # Create test data
        engine = StructuredTutoringEngine()
        
        test_problem = Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
            difficulty="easy",
            concepts=["lists", "loops", "input"],
            starter_code="",
            solution_template="",
            test_cases=[],
            hints=[]
        )
        
        # Test the _guide_with_questions method directly
        print("\n🎯 Testing _guide_with_questions method...")
        
        test_inputs = [
            "I want to use a for loop",
            "How do I take user input?", 
            "I'm confused about this problem",
            "What should I do next?"
        ]
        
        for i, user_input in enumerate(test_inputs, 1):
            print(f"\n📤 Test {i}: '{user_input}'")
            
            try:
                response = await engine._guide_with_questions(user_input, test_problem)
                print(f"✅ Response: '{response}'")
                
                # Check if it's the fallback response
                if response == "Can you think about what the problem is asking you to do step by step?":
                    print("🚨 FALLBACK RESPONSE DETECTED! OpenAI call failed!")
                else:
                    print("✅ OpenAI call succeeded - got dynamic response")
                    
            except Exception as e:
                print(f"❌ Error in _guide_with_questions: {e}")
                import traceback
                traceback.print_exc()
                
        # Test the OpenAI client directly with the same parameters
        print("\n🤖 Testing OpenAI client directly with same parameters...")
        
        from app.models import ConversationMessage, MessageType
        from datetime import datetime
        
        system_prompt = f"""You are guiding a student through this problem: {test_problem.description}

The student said: "I want to use a for loop"

Respond with a SINGLE guiding question that helps them think through the next step. Do NOT provide solutions or direct answers. Ask questions that lead them to discover the answer themselves.

Examples:
- "What type of data does input() return?"
- "How many times do you need to repeat the input process?"
- "What should you append to the list - the loop counter or the user's input?"

Keep your response to ONE question only."""
        
        user_message = ConversationMessage(
            timestamp=datetime.utcnow(),
            message_type=MessageType.USER,
            content="The student said: 'I want to use a for loop'"
        )
        
        try:
            response = await engine.openai_client.generate_response(
                messages=[user_message],
                system_prompt=system_prompt,
                max_tokens=100,
                temperature=0.3
            )
            
            print(f"📊 OpenAI Response Success: {response.get('success', False)}")
            if response.get("success"):
                print(f"✅ OpenAI Content: '{response.get('content', 'No content')}'")
            else:
                print(f"❌ OpenAI Error: {response.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Direct OpenAI client error: {e}")
            import traceback
            traceback.print_exc()
            
        # Check OpenAI client configuration
        print("\n🔧 Checking OpenAI client configuration...")
        
        try:
            from app.core.config import settings
            print(f"✅ OpenAI Model: {getattr(settings, 'OPENAI_MODEL', 'Not set')}")
            print(f"✅ OpenAI API Key Length: {len(getattr(settings, 'OPENAI_API_KEY', ''))}")
            
            # Check if the API key is valid format
            api_key = getattr(settings, 'OPENAI_API_KEY', '')
            if api_key.startswith('sk-'):
                print("✅ API key has correct format (starts with sk-)")
            else:
                print("❌ API key does NOT have correct format (should start with sk-)")
                
        except Exception as e:
            print(f"❌ Error checking configuration: {e}")
            
    except Exception as e:
        print(f"❌ Error in debug setup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Make sure we're in the right directory
    os.chdir("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
    
    try:
        asyncio.run(debug_openai_calls())
    except KeyboardInterrupt:
        print("\n👋 Debug interrupted by user")
    except Exception as e:
        print(f"\n💥 Debug failed with error: {e}")
        import traceback
        traceback.print_exc()