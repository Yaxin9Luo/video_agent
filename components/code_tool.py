import os
import tempfile
import subprocess
from typing import Dict, Any, List, Optional
from agents import function_tool

@function_tool
def execute_python_code(code: str) -> Dict[str, Any]:
    """
    Execute Python code and return the result.
    
    Args:
        code: Python code to execute
        
    Returns:
        Dictionary containing the execution result
    """
    # 使用空字典作为默认输入
    inputs = {}
    
    # Create a temporary directory for code execution
    temp_dir = tempfile.mkdtemp()
    script_path = os.path.join(temp_dir, "script.py")
    
    # Write the code to a temporary file
    with open(script_path, "w") as f:
        f.write(code)
    
    # Write inputs to a JSON file
    inputs_path = os.path.join(temp_dir, "inputs.json")
    with open(inputs_path, "w") as f:
        import json
        json.dump(inputs, f)

    # Create a wrapper script that loads inputs and executes the code
    wrapper_path = os.path.join(temp_dir, "wrapper.py")
    with open(wrapper_path, "w") as f:
        f.write("""
import json
import sys
import os

# 使用绝对路径加载 inputs.json
script_dir = os.path.dirname(os.path.abspath(__file__))
inputs_path = os.path.join(script_dir, "inputs.json")

# Load inputs
with open(inputs_path, "r") as f:
    inputs = json.load(f)

# Add the current directory to sys.path
sys.path.insert(0, os.getcwd())

# Execute the script with inputs in its namespace
namespace = inputs.copy()
script_path = os.path.join(script_dir, "script.py")
with open(script_path, "r") as script_file:
    exec(script_file.read(), namespace)

# Save outputs
outputs = {}
for key, value in namespace.items():
    # Only include non-function, non-module, non-private variables
    if (not key.startswith("__") and 
        not callable(value) and 
        not key in inputs and
        not key == "inputs"):
        try:
            # Try to serialize the value to JSON
            json.dumps({key: value})
            outputs[key] = value
        except (TypeError, OverflowError):
            # Skip values that can't be serialized
            pass

outputs_path = os.path.join(script_dir, "outputs.json")
with open(outputs_path, "w") as f:
    json.dump(outputs, f)
""")
    
    try:
        # Execute the wrapper script
        process = subprocess.run(
            ["python", wrapper_path],
            cwd=os.getcwd(),  # 使用当前工作目录
            capture_output=True,
            text=True,
            timeout=60  # Timeout after 60 seconds
        )
        
        # Check for errors
        if process.returncode != 0:
            return {
                "status": "error",
                "message": f"Code execution failed: {process.stderr}",
                "stdout": process.stdout,
                "stderr": process.stderr
            }
        
        # Load outputs
        outputs_path = os.path.join(temp_dir, "outputs.json")
        if os.path.exists(outputs_path):
            with open(outputs_path, "r") as f:
                import json
                outputs = json.load(f)
        else:
            outputs = {}
        
        return {
            "status": "success",
            "message": "Code executed successfully",
            "stdout": process.stdout,
            "stderr": process.stderr,
            "outputs": outputs
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Code execution timed out after 60 seconds"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error executing code: {str(e)}"
        }
    finally:
        # Clean up temporary files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

@function_tool
def get_installed_packages() -> List[str]:
    """
    Get a list of installed Python packages.
    
    Returns:
        List of installed package names
    """
    try:
        process = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True,
            text=True
        )
        
        if process.returncode != 0:
            return []
        
        import json
        packages = json.loads(process.stdout)
        return [package["name"] for package in packages]
    except Exception:
        return []