"""
Code Execution Service - Secure Python code execution for the AI tutoring system
This service provides safe, sandboxed execution of student Python code.
"""

import subprocess
import tempfile
import os
import signal
import time
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class CodeExecutionResult:
    """Result of code execution"""
    
    def __init__(self, output: str = "", error: str = "", execution_time: float = 0.0, success: bool = False):
        self.output = output
        self.error = error
        self.execution_time = execution_time
        self.success = success
        self.timestamp = datetime.utcnow()


class CodeExecutionService:
    """Service for executing Python code safely"""
    
    def __init__(self):
        self.max_execution_time = 10  # seconds
        self.max_output_length = 10000  # characters
        
        # Security: Restricted imports and functions
        self.forbidden_imports = [
            'os', 'sys', 'subprocess', 'shutil', 'pathlib', 'glob',
            'socket', 'urllib', 'requests', 'http', 'ftplib', 'smtplib',
            'pickle', 'marshal', 'shelve', 'dbm', 'sqlite3',
            'threading', 'multiprocessing', 'asyncio',
            'ctypes', 'struct', 'mmap', 'tempfile',
            '__import__', 'exec', 'eval', 'compile', 'open'
        ]
        
        # Allowed built-ins for educational purposes
        self.allowed_builtins = [
            'print', 'input', 'len', 'range', 'str', 'int', 'float',
            'list', 'dict', 'set', 'tuple', 'bool', 'type', 'isinstance',
            'hasattr', 'getattr', 'setattr', 'enumerate', 'zip', 'map',
            'filter', 'sorted', 'sum', 'min', 'max', 'abs', 'round',
            'any', 'all', 'chr', 'ord', 'bin', 'hex', 'oct'
        ]
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """Validate code for security issues"""
        
        # Check for forbidden imports
        for forbidden in self.forbidden_imports:
            if re.search(rf'\b(import\s+{forbidden}|from\s+{forbidden})', code):
                return {
                    "valid": False,
                    "error": f"Import '{forbidden}' is not allowed for security reasons"
                }
        
        # Check for dangerous function calls
        dangerous_patterns = [
            r'__.*__',  # Dunder methods
            r'exec\s*\(',  # exec function
            r'eval\s*\(',  # eval function
            r'compile\s*\(',  # compile function
            r'open\s*\(',  # file operations
            r'file\s*\(',  # file operations
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, code):
                return {
                    "valid": False,
                    "error": f"Pattern '{pattern}' is not allowed for security reasons"
                }
        
        # Check code length
        if len(code) > 5000:
            return {
                "valid": False,
                "error": "Code is too long. Please keep it under 5000 characters."
            }
        
        return {"valid": True}
    
    def create_safe_execution_script(self, code: str) -> str:
        """Create a safe execution wrapper for the user code"""
        
        # Properly indent the user code
        indented_code = '\n'.join('    ' + line for line in code.split('\n'))
        
        # Create the complete script with proper indentation
        script = f"""
import sys
from io import StringIO

# Simulate input() with predefined values for demonstration
_input_values = ['10', '20', '30', '40', '50']  # Example inputs
_input_index = 0

def input(prompt=""):
    global _input_index
    if prompt:
        print(prompt, end="")
    if _input_index < len(_input_values):
        value = _input_values[_input_index]
        _input_index += 1
        print(value)  # Echo the input
        return value
    return ""

# Redirect stdout to capture output
old_stdout = sys.stdout
sys.stdout = mystdout = StringIO()

try:
    # User code execution (properly indented)
{indented_code}
except Exception as e:
    print(f"Error: {{e}}")
finally:
    # Restore stdout and get output
    sys.stdout = old_stdout
    output = mystdout.getvalue()
    print(output, end="")
"""
        
        return script
    
    async def execute_code(self, code: str, mock_inputs: Optional[list] = None) -> CodeExecutionResult:
        """Execute Python code safely"""
        
        logger.info(f"🚀 CODE_EXECUTION_SERVICE: Executing code (length: {len(code)})")
        logger.info(f"💻 CODE_EXECUTION_SERVICE: Code preview: {code[:100]}...")
        
        start_time = time.time()
        
        try:
            # Validate code first
            validation = self.validate_code(code)
            if not validation["valid"]:
                logger.error(f"❌ CODE_EXECUTION_SERVICE: Code validation failed: {validation['error']}")
                return CodeExecutionResult(
                    error=validation["error"],
                    execution_time=0.0,
                    success=False
                )
            
            # Create safe execution script
            safe_code = self.create_safe_execution_script(code)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(safe_code)
                temp_file_path = temp_file.name
            
            try:
                # Execute with timeout
                logger.info("⚡ CODE_EXECUTION_SERVICE: Running Python subprocess...")
                
                process = subprocess.Popen(
                    ['/usr/bin/python3', temp_file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    preexec_fn=os.setsid  # Create new process group
                )
                
                try:
                    stdout, stderr = process.communicate(timeout=self.max_execution_time)
                except subprocess.TimeoutExpired:
                    # Kill the process group
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.communicate()  # Clean up
                    
                    logger.error("⏰ CODE_EXECUTION_SERVICE: Code execution timeout")
                    return CodeExecutionResult(
                        error=f"Code execution timed out after {self.max_execution_time} seconds",
                        execution_time=self.max_execution_time,
                        success=False
                    )
                
                execution_time = time.time() - start_time
                
                # Process results
                if process.returncode == 0:
                    # Successful execution
                    output = stdout.strip()
                    if len(output) > self.max_output_length:
                        output = output[:self.max_output_length] + "\n... (output truncated)"
                    
                    logger.info(f"✅ CODE_EXECUTION_SERVICE: Execution successful (time: {execution_time:.2f}s)")
                    logger.info(f"📤 CODE_EXECUTION_SERVICE: Output: {output[:100]}...")
                    
                    return CodeExecutionResult(
                        output=output,
                        execution_time=execution_time,
                        success=True
                    )
                else:
                    # Execution error
                    error_message = stderr.strip()
                    if len(error_message) > self.max_output_length:
                        error_message = error_message[:self.max_output_length] + "\n... (error truncated)"
                    
                    logger.error(f"❌ CODE_EXECUTION_SERVICE: Execution failed: {error_message}")
                    
                    return CodeExecutionResult(
                        error=error_message,
                        execution_time=execution_time,
                        success=False
                    )
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
                    
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"💥 CODE_EXECUTION_SERVICE: Unexpected error: {e}")
            
            return CodeExecutionResult(
                error=f"Execution error: {str(e)}",
                execution_time=execution_time,
                success=False
            )
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution service statistics"""
        return {
            "max_execution_time": self.max_execution_time,
            "max_output_length": self.max_output_length,
            "forbidden_imports_count": len(self.forbidden_imports),
            "allowed_builtins_count": len(self.allowed_builtins)
        }


# Create service instance
code_execution_service = CodeExecutionService()