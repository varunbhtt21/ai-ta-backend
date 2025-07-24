#!/usr/bin/env python3
"""
Test script to verify if structured tutoring API is working correctly
and actually calling OpenAI or returning hardcoded responses.
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"

class StructuredTutoringTester:
    def __init__(self):
        self.client = httpx.AsyncClient()
        self.auth_token = None
        self.session_id = None
        self.assignment_id = "675a123456789012345678ab"  # Example assignment ID
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def authenticate(self) -> bool:
        """Authenticate and get auth token"""
        print("🔐 Step 1: Authenticating...")
        
        try:
            # Try to login first
            login_response = await self.client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "email": TEST_USER_EMAIL,
                    "password": TEST_USER_PASSWORD
                }
            )
            
            if login_response.status_code == 200:
                data = login_response.json()
                self.auth_token = data.get("data", {}).get("access_token")
                print(f"✅ Login successful! Token: {self.auth_token[:20]}...")
                return True
            else:
                print(f"❌ Login failed: {login_response.status_code} - {login_response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    async def start_structured_session(self) -> bool:
        """Start a structured tutoring session"""
        print("\n🚀 Step 2: Starting structured tutoring session...")
        
        if not self.auth_token:
            print("❌ No auth token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            response = await self.client.post(
                f"{BASE_URL}/structured/start",
                json={"assignment_id": self.assignment_id},
                headers=headers
            )
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📄 Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Session started successfully!")
                print(f"📋 Response Data: {json.dumps(data, indent=2)}")
                
                session_data = data.get("data", {})
                self.session_id = session_data.get("session_id")
                print(f"🆔 Session ID: {self.session_id}")
                return True
            else:
                print(f"❌ Failed to start session: {response.status_code}")
                print(f"📄 Error Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting session: {e}")
            return False
    
    async def send_test_messages(self) -> None:
        """Send various test messages to check if OpenAI is being called"""
        print("\n💬 Step 3: Testing message sending...")
        
        if not self.session_id:
            print("❌ No session ID available")
            return
            
        test_messages = [
            {
                "message": "Hello, I'm ready to start!",
                "description": "Initial greeting - should present problem"
            },
            {
                "message": "give me the problem statement?",
                "description": "Requesting problem statement - should provide actual problem"
            },
            {
                "message": "I want to use a for loop to get 5 inputs",
                "description": "Student approach - should validate approach"
            },
            {
                "message": "x = input()\ny = []\ny.append(x)",
                "description": "Code submission - should analyze code"
            },
            {
                "message": "I don't understand this problem",
                "description": "Confused student - should break down problem"
            }
        ]
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        for i, test in enumerate(test_messages, 1):
            print(f"\n📝 Test Message {i}: {test['description']}")
            print(f"📤 Sending: '{test['message']}'")
            
            try:
                # Send message with problem context
                response = await self.client.post(
                    f"{BASE_URL}/structured/message",
                    json={
                        "session_id": self.session_id,
                        "message": test["message"],
                        "problem_context": {
                            "title": "Create a List with User Input",
                            "description": "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.",
                            "concepts": ["lists", "loops", "input"],
                            "difficulty": "easy"
                        }
                    },
                    headers=headers
                )
                
                print(f"📊 Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    response_data = data.get("data", {})
                    ai_message = response_data.get("message", "No message")
                    student_state = response_data.get("student_state", "unknown")
                    tutoring_mode = response_data.get("tutoring_mode", "unknown")
                    
                    print(f"✅ AI Response: '{ai_message}'")
                    print(f"📊 Student State: {student_state}")
                    print(f"🎯 Tutoring Mode: {tutoring_mode}")
                    
                    # Check if response looks hardcoded
                    hardcoded_indicators = [
                        "Can you think about what the problem is asking",
                        "What will you use to store the numbers",
                        "What do you think you need to do"
                    ]
                    
                    is_hardcoded = any(indicator in ai_message for indicator in hardcoded_indicators)
                    if is_hardcoded:
                        print("⚠️  WARNING: This looks like a hardcoded response!")
                    else:
                        print("✅ Response appears to be dynamically generated")
                        
                else:
                    print(f"❌ Failed to send message: {response.status_code}")
                    print(f"📄 Error: {response.text}")
                    
            except Exception as e:
                print(f"❌ Error sending message: {e}")
            
            # Wait between messages
            await asyncio.sleep(1)
    
    async def check_openai_integration(self) -> None:
        """Check if OpenAI integration is properly configured"""
        print("\n🤖 Step 4: Checking OpenAI Integration...")
        
        # Try to make a direct test to the backend's OpenAI service
        if not self.auth_token:
            print("❌ No auth token available")
            return
            
        # Check if there are any OpenAI-related endpoints
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        try:
            # Check if we can get session status
            if self.session_id:
                response = await self.client.get(
                    f"{BASE_URL}/structured/{self.session_id}/status",
                    headers=headers
                )
                
                print(f"📊 Session Status Response: {response.status_code}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"📋 Session Status: {json.dumps(data, indent=2)}")
                    
        except Exception as e:
            print(f"❌ Error checking OpenAI integration: {e}")

async def main():
    """Main test function"""
    print("🧪 STRUCTURED TUTORING API TEST")
    print("=" * 50)
    
    async with StructuredTutoringTester() as tester:
        # Step 1: Authenticate
        if not await tester.authenticate():
            print("\n❌ Authentication failed. Please check:")
            print("1. Backend is running on http://localhost:8000")
            print("2. Test user exists or registration is working")
            return
        
        # Step 2: Start session
        if not await tester.start_structured_session():
            print("\n❌ Session creation failed. Please check:")
            print("1. Assignment ID exists in database")
            print("2. Structured sessions API is working")
            return
        
        # Step 3: Test messaging
        await tester.send_test_messages()
        
        # Step 4: Check OpenAI integration
        await tester.check_openai_integration()
    
    print("\n" + "=" * 50)
    print("🏁 TEST COMPLETED")
    print("\nIf you see hardcoded responses, the issue is likely:")
    print("1. ❌ OpenAI API key not configured")
    print("2. ❌ OpenAI client not being called")
    print("3. ❌ Fallback responses being returned")
    print("4. ❌ Error in OpenAI integration")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)