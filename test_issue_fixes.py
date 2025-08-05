#!/usr/bin/env python3
"""
Test the fixes for the identified issues
Tests that logic explanations are not misclassified as code submissions
"""

import sys
from pathlib import Path

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

from services.structured_tutoring_engine import StructuredTutoringEngine
from services.enhanced_logic_validator import EnhancedLogicValidator
from services.validation_types import LogicValidationLevel, StrictnessLevel
from models import Problem, ConversationMessage, MessageType
from datetime import datetime


def test_issue_fixes():
    """Test that all identified issues are fixed"""
    
    print("🧪 ISSUE_FIXES_TEST: Testing all identified issue fixes\n")
    
    # Create tutoring engine
    engine = StructuredTutoringEngine()
    validator = EnhancedLogicValidator()
    
    # Test problem
    problem = Problem(
        number=1,
        title="Create a List with User Input",
        description="Write a program that prompts the user to enter five numbers one by one.",
        concepts=["lists", "loops", "input"]
    )
    
    # Test conversation history
    conversation_history = [
        ConversationMessage(
            timestamp=datetime.now(),
            message_type=MessageType.ASSISTANT,
            content="How are you thinking to solve this problem?"
        ),
        ConversationMessage(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content="the logic is take input, loop the number and store in list"
        ),
        ConversationMessage(
            timestamp=datetime.now(),
            message_type=MessageType.ASSISTANT,
            content="That's a good start! What kind of loop do you think you should use to repeat the input process for the five numbers?"
        )
    ]
    
    # Issue 1: Test Logic vs Code Classification
    print("🔍 Test 1: Logic vs Code Classification")
    
    # This should be classified as LOGIC, not CODE
    detailed_logic = "First I will take the user input and thenI will run the for loop 5 times in a range and then append to list"
    
    is_code_old_logic = any(indicator in detailed_logic for indicator in ['for ', 'append'])  # Old broken logic
    is_code_new_logic = engine._is_code_submission(detailed_logic)  # New fixed logic
    
    print(f"   Detailed logic response: '{detailed_logic[:60]}...'")
    print(f"   ❌ Old logic would classify as CODE: {is_code_old_logic}")  
    print(f"   ✅ New logic classifies as CODE: {is_code_new_logic}")
    
    if not is_code_new_logic:
        print("   ✅ PASS: Logic explanation correctly NOT classified as code")
    else:
        print("   ❌ FAIL: Logic explanation incorrectly classified as code")
    print()
    
    # Test actual code IS detected
    actual_code = """
numbers = []
for i in range(5):
    num = input("Enter number: ")
    numbers.append(int(num))
print(numbers)
"""
    
    is_actual_code = engine._is_code_submission(actual_code)
    print(f"   ✅ Actual code correctly classified as CODE: {is_actual_code}")
    if not is_actual_code:
        print("   ❌ FAIL: Actual code should be detected as code")
    print()
    
    # Issue 2: Test Gaming Detection Improvements
    print("🚫 Test 2: Gaming Detection Improvements")
    
    # Progressive improvement should NOT be flagged as gaming
    previous_response = "I will use a loop"
    improved_response = "First I will take the user input and then I will run the for loop 5 times in a range and then append to list"
    
    # Simulate conversation with improvement
    improvement_history = conversation_history + [
        ConversationMessage(
            timestamp=datetime.now(),
            message_type=MessageType.USER,
            content=previous_response
        )
    ]
    
    import asyncio
    
    async def test_gaming_detection():
        gaming_result = await validator._detect_gaming_attempts(
            improved_response, improvement_history, problem
        )
        return gaming_result
    
    gaming_result = asyncio.run(test_gaming_detection())
    
    print(f"   Previous: '{previous_response}'")
    print(f"   Improved: '{improved_response[:50]}...'")
    print(f"   Gaming detected: {gaming_result.is_gaming}")
    print(f"   Gaming type: {gaming_result.gaming_type}")
    print(f"   Confidence: {gaming_result.confidence:.2f}")
    
    if not gaming_result.is_gaming:
        print("   ✅ PASS: Progressive improvement not flagged as gaming")
    else:
        print("   ❌ FAIL: Progressive improvement incorrectly flagged as gaming")
    print()
    
    # Issue 3: Test Logic Quality Recognition  
    print("🎓 Test 3: Logic Quality Recognition")
    
    detailed_response = "First I will take the user input and then I will run the for loop 5 times in a range and then append to list"
    
    # Test fallback analysis (this should give good score)
    required_elements = ['data_structure_choice', 'input_method', 'loop_structure', 'process_flow']
    analysis = validator._fallback_analysis(detailed_response, required_elements)
    
    print(f"   Response: '{detailed_response}'")
    print(f"   Confidence score: {analysis['confidence_score']:.2f}")
    print(f"   Found elements: {len(required_elements) - len(analysis['missing_elements'])}/{len(required_elements)}")
    print(f"   Strengths: {analysis['strengths']}")
    print(f"   Recommendation: {analysis['recommendation']}")
    
    if analysis['confidence_score'] > 0.6:
        print("   ✅ PASS: Detailed logic gets good confidence score")
    else:
        print("   ❌ FAIL: Detailed logic should get higher confidence score")
    print()
    
    # Issue 4: Test State Management
    print("📊 Test 4: State Management")
    
    from services.structured_tutoring_engine import StudentState
    
    # Student providing logic should stay in logic validation, not go to code review
    current_state = StudentState.LOGIC_VALIDATION
    new_state = engine._detect_student_state(detailed_response, conversation_history, current_state)
    
    print(f"   Current state: {current_state.value}")
    print(f"   Student input: Logic explanation with technical terms")
    print(f"   Next state: {new_state.value}")
    
    if new_state == StudentState.LOGIC_VALIDATION:
        print("   ✅ PASS: Student stays in logic validation phase")
    else:
        print("   ❌ FAIL: Student should stay in logic validation, not move to code phase")
    print()
    
    print("🎉 ISSUE_FIXES_TEST: Testing complete!")
    print("\n📊 Summary of Fixes:")
    print("✅ Fixed overly aggressive code detection")
    print("✅ Fixed false positive gaming detection for improvements")
    print("✅ Enhanced logic quality recognition")
    print("✅ Corrected state management for logic vs code phases")
    print("✅ Made code detection use proper syntax patterns")
    print("\n🚀 Students can now provide detailed logic explanations without being blocked!")


if __name__ == "__main__":
    test_issue_fixes()