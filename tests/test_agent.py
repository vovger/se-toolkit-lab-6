import subprocess
import json
import sys

def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with answer and tool_calls fields."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    # Check exit code
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}"
    
    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {result.stdout}\nError: {e}"
    
    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
    
    # Check that answer is not empty
    assert output["answer"], "'answer' field is empty"
    
    # Check that debug output goes to stderr
    assert "[DEBUG]" in result.stderr or result.stderr == "", "Expected debug info in stderr"
