#!/usr/bin/env python3
"""
Test the full API flow from frontend to backend to simulate the exact issue
"""

import asyncio
import httpx
import json
import os

async def test_full_api_flow():
    """Test the complete API flow to see where hardcoded responses come from"""
    
    print("🚀 TESTING FULL API FLOW")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Step 1: Start a structured session (skip auth for now)
        print("\n📡 Step 1: Testing /structured/start endpoint...")
        
        try:
            # We need to test without auth first to see the raw API behavior
            start_response = await client.post(
                "http://localhost:8000/structured/start",
                json={"assignment_id": "675a123456789012345678ab"}  # Example assignment ID
            )
            
            print(f"📊 Response Status: {start_response.status_code}")
            print(f"📄 Response Body: {start_response.text}")
            
            if start_response.status_code == 401:
                print("⚠️  Got 401 Unauthorized - this is expected without auth")
                print("🔍 Let's check what the structured sessions router is actually returning...")
                
                # Let's check if the endpoint exists
                health_response = await client.get("http://localhost:8000/health")
                print(f"✅ Health check: {health_response.json()}")
                
        except Exception as e:
            print(f"❌ Error testing /structured/start: {e}")
        
        # Step 2: Let's check the routes directly
        print("\n🔍 Step 2: Let's investigate the actual API routes...")
        
        try:
            # Check if we can get the OpenAPI docs to see available routes
            docs_response = await client.get("http://localhost:8000/docs")
            print(f"📊 Docs Status: {docs_response.status_code}")
            
            # Try to get the OpenAPI schema
            openapi_response = await client.get("http://localhost:8000/openapi.json")
            if openapi_response.status_code == 200:
                openapi_data = openapi_response.json()
                
                # Look for structured routes
                structured_routes = []
                for path, methods in openapi_data.get("paths", {}).items():
                    if "structured" in path.lower():
                        structured_routes.append(path)
                
                if structured_routes:
                    print("✅ Found structured routes:")
                    for route in structured_routes:
                        print(f"   📍 {route}")
                else:
                    print("❌ No structured routes found in OpenAPI schema!")
                    print("🔍 This might be why frontend calls are failing!")
                    
                    # Let's see what routes ARE available
                    print("\n🔍 Available routes:")
                    for path in list(openapi_data.get("paths", {}).keys())[:10]:  # First 10 routes
                        print(f"   📍 {path}")
                        
            else:
                print(f"❌ Could not get OpenAPI schema: {openapi_response.status_code}")
                
        except Exception as e:
            print(f"❌ Error checking API routes: {e}")
            
        # Step 3: Check if the backend is loading the structured sessions router
        print("\n🔧 Step 3: Checking if structured sessions router is loaded...")
        
        try:
            # Import the main app to see what routers are included
            import sys
            sys.path.append("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
            
            from app.main import app
            
            # Check the routes in the FastAPI app
            routes = []
            for route in app.routes:
                if hasattr(route, 'path'):
                    routes.append(route.path)
            
            structured_routes = [r for r in routes if 'structured' in r.lower()]
            
            if structured_routes:
                print("✅ Found structured routes in app:")
                for route in structured_routes:
                    print(f"   📍 {route}")
            else:
                print("❌ No structured routes found in FastAPI app!")
                print("🔍 This confirms the router is not being included properly!")
                
                # Show what routes ARE included
                print("\n🔍 Available routes in app:")
                for route in routes[:15]:  # First 15 routes
                    print(f"   📍 {route}")
                    
        except Exception as e:
            print(f"❌ Error checking app routes: {e}")
            import traceback
            traceback.print_exc()
            
        # Step 4: Let's manually check the router inclusion
        print("\n📋 Step 4: Checking router inclusion in main.py...")
        
        try:
            # Check if structured_sessions is imported and included
            with open("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend/app/main.py", "r") as f:
                main_content = f.read()
                
            if "structured_sessions" in main_content:
                print("✅ structured_sessions is imported in main.py")
                
                # Check if it's included as a router
                if "structured_sessions.router" in main_content:
                    print("✅ structured_sessions.router is included")
                    
                    # Extract the router inclusion line
                    lines = main_content.split('\n')
                    for line in lines:
                        if "structured_sessions.router" in line:
                            print(f"📍 Router inclusion: {line.strip()}")
                else:
                    print("❌ structured_sessions.router is NOT included!")
            else:
                print("❌ structured_sessions is NOT imported in main.py!")
                
        except Exception as e:
            print(f"❌ Error checking main.py: {e}")

if __name__ == "__main__":
    # Make sure we're in the right directory
    os.chdir("/Users/varunbhatt/Downloads/2025/Jazzee/Projects/AI-TA/ai-ta-backend")
    
    try:
        asyncio.run(test_full_api_flow())
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()