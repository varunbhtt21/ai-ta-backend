#!/usr/bin/env python3
"""
Test the structured API with proper authentication to simulate frontend behavior
"""

import asyncio
import httpx
import json
import os

async def test_with_auth():
    """Test with authentication to see actual API responses"""
    
    print("🔐 TESTING WITH AUTHENTICATION")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Step 1: Create a test user (or try to login with existing user)
        print("\n👤 Step 1: Setting up authentication...")
        
        test_user = {
            "email": "test@example.com",
            "password": "testpassword123",
            "full_name": "Test User",
            "role": "student"
        }
        
        auth_token = None
        
        try:
            # Try to register user first
            register_response = await client.post(
                "http://localhost:8000/auth/register",
                json=test_user
            )
            
            if register_response.status_code == 201:
                print("✅ User registered successfully")
                auth_data = register_response.json()
                auth_token = auth_data.get("data", {}).get("access_token")
            elif register_response.status_code == 400:
                # User might already exist, try login
                print("ℹ️  User might exist, trying login...")
                login_response = await client.post(
                    "http://localhost:8000/auth/login",
                    json={
                        "email": test_user["email"],
                        "password": test_user["password"]
                    }
                )
                
                if login_response.status_code == 200:
                    print("✅ User logged in successfully")
                    auth_data = login_response.json()
                    auth_token = auth_data.get("data", {}).get("access_token")
                else:
                    print(f"❌ Login failed: {login_response.status_code} - {login_response.text}")
            else:
                print(f"❌ Registration failed: {register_response.status_code} - {register_response.text}")
                
        except Exception as e:
            print(f"❌ Auth setup error: {e}")
            
        if not auth_token:
            print("❌ Could not get authentication token. Exiting.")
            return
            
        print(f"✅ Got auth token: {auth_token[:20]}...")
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Step 2: Create or get an assignment
        print("\n📚 Step 2: Setting up assignment...")
        
        try:
            # Try to get existing assignments
            assignments_response = await client.get(
                "http://localhost:8000/assignments",
                headers=headers
            )
            
            assignment_id = None
            if assignments_response.status_code == 200:
                assignments_data = assignments_response.json()
                assignments = assignments_data.get("data", [])
                if assignments:
                    assignment_id = assignments[0]["id"]
                    print(f"✅ Using existing assignment: {assignment_id}")
                else:
                    print("ℹ️  No assignments found")
            else:
                print(f"⚠️  Could not get assignments: {assignments_response.status_code}")
                
            # If no assignment, we'll use a mock ID for testing
            if not assignment_id:
                print("ℹ️  Using mock assignment ID for testing")
                assignment_id = "675a123456789012345678ab"
                
        except Exception as e:
            print(f"❌ Assignment setup error: {e}")
            assignment_id = "675a123456789012345678ab"
            
        # Step 3: Start structured session
        print("\n🚀 Step 3: Starting structured session...")
        
        try:
            start_response = await client.post(
                "http://localhost:8000/structured/start",
                json={"assignment_id": assignment_id},
                headers=headers
            )
            
            print(f"📊 Start Session Status: {start_response.status_code}")
            print(f"📄 Start Session Response: {start_response.text}")
            
            session_id = None
            if start_response.status_code == 200:
                start_data = start_response.json()
                session_data = start_data.get("data", {})
                session_id = session_data.get("session_id")
                print(f"✅ Session started! ID: {session_id}")
                print(f"📝 Welcome message: {session_data.get('message', 'No message')}")
            else:
                print(f"❌ Failed to start session: {start_response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ Session start error: {e}")
            return
            
        # Step 4: Test message sending - simulate frontend behavior
        print("\n💬 Step 4: Testing message sending...")
        
        test_messages = [
            "give me the problem statement?",
            "explain the problem statement?", 
            "what am i supposed to do?"
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n📤 Test Message {i}: '{message}'")
            
            try:
                # Send exactly like the frontend does
                message_response = await client.post(
                    "http://localhost:8000/structured/message",
                    json={
                        "session_id": session_id,
                        "message": message,
                        "problem_context": {
                            "title": "Create a List with User Input",
                            "description": "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
                            "concepts": ["lists", "loops", "input"],
                            "difficulty": "easy"
                        }
                    },
                    headers=headers
                )
                
                print(f"📊 Response Status: {message_response.status_code}")
                
                if message_response.status_code == 200:
                    response_data = message_response.json()
                    message_data = response_data.get("data", {})
                    ai_response = message_data.get("message", "No message")
                    
                    print(f"✅ AI Response: '{ai_response}'")
                    print(f"📊 Student State: {message_data.get('student_state', 'unknown')}")
                    print(f"🎯 Tutoring Mode: {message_data.get('tutoring_mode', 'unknown')}")
                    
                    # Check if this is the problematic hardcoded response
                    hardcoded_patterns = [
                        "What will you use to store the numbers that the user inputs?",
                        "What do you think you need to do with the numbers after the user enters them?",
                        "Can you think about what the problem is asking you to do step by step?"
                    ]
                    
                    is_hardcoded = any(pattern in ai_response for pattern in hardcoded_patterns)
                    if is_hardcoded:
                        print("🚨 FOUND THE ISSUE! This IS a hardcoded response!")
                        print("🔍 The backend is returning hardcoded responses despite OpenAI working")
                    else:
                        # Check if it contains the actual problem description
                        if "Write a program that prompts the user to enter 5 numbers" in ai_response:
                            print("✅ Response contains actual problem description - WORKING CORRECTLY!")
                        else:
                            print("⚠️  Response doesn't contain expected problem description")
                            
                else:
                    print(f"❌ Message failed: {message_response.status_code}")
                    print(f"📄 Error: {message_response.text}")
                    
            except Exception as e:
                print(f"❌ Message error: {e}")
                
            print("-" * 40)

if __name__ == "__main__":
    # Make sure we're in the right directory
    os.chdir("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
    
    try:
        asyncio.run(test_with_auth())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()