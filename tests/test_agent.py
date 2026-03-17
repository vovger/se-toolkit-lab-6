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


def test_agent_reads_source_code_for_framework_question():
    """Test that agent reads backend source code when asked about the framework."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What Python web framework does this project's backend use? Read the source code to find out."],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {result.stdout}\nError: {e}"

    # Check required fields
    assert "answer" in output
    assert "tool_calls" in output

    # Verify that read_file was called on backend code
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    read_file_calls = [tc for tc in tool_calls if tc["tool"] == "read_file"]
    assert len(read_file_calls) > 0, "Expected read_file to be called for code question"

    # Verify it read a backend file (main.py or similar)
    backend_paths = ["backend/app/main.py", "src/app/main.py", "main.py"]
    called_paths = [tc["args"]["path"] for tc in read_file_calls]
    assert any(bp in cp for bp in backend_paths for cp in called_paths), \
        f"Expected to read backend file, got paths: {called_paths}"

    # Verify answer mentions FastAPI
    answer = output["answer"].lower()
    assert "fastapi" in answer, f"Expected answer to mention FastAPI, got: {output['answer']}"


def test_agent_uses_query_api_for_item_count():
    """Test that agent uses query_api when asked about item count in database."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How many items are currently stored in the database? Query the running API to find out."],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {result.stdout}\nError: {e}"

    # Check required fields
    assert "answer" in output
    assert "tool_calls" in output

    # Verify that query_api was called
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    query_api_calls = [tc for tc in tool_calls if tc["tool"] == "query_api"]
    assert len(query_api_calls) > 0, "Expected query_api to be called for data question"

    # Verify it called the items endpoint
    items_endpoint_called = any(
        "/items" in str(tc["args"].get("path", ""))
        for tc in query_api_calls
    )
    assert items_endpoint_called, \
        f"Expected query_api to call /items endpoint, got: {[tc['args'] for tc in query_api_calls]}"

    # Verify answer contains a number
    answer = output["answer"]
    import re
    numbers = re.findall(r'\d+', answer)
    assert len(numbers) > 0, f"Expected answer to contain a number, got: {answer}"
def test_agent_uses_list_files_for_wiki_question():
    """Test that agent calls list_files when asked about wiki contents."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {result.stdout}\nError: {e}"

    # Check required fields
    assert "answer" in output
    assert "source" in output
    assert "tool_calls" in output

    # Verify that list_files was called
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    list_files_calls = [tc for tc in tool_calls if tc["tool"] == "list_files"]
    assert len(list_files_calls) > 0, "Expected list_files to be called"

    # Verify it listed wiki directory (accept both "wiki" and "wiki/")
    wiki_path = list_files_calls[0]["args"]["path"]
    assert wiki_path in ["wiki", "wiki/"], f"Expected wiki path, got: {wiki_path}"

def test_agent_uses_read_file_for_merge_conflict():
    """Test that agent reads git.md when asked about merge conflicts."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How do I resolve merge conflicts according to the wiki?"],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    assert result.returncode == 0, f"Agent failed with exit code {result.returncode}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        assert False, f"Output is not valid JSON: {result.stdout}\nError: {e}"
    
    # Check required fields
    assert "answer" in output
    assert "source" in output
    assert "tool_calls" in output
    
    # Verify that read_file was called on git.md
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"
    
    read_file_calls = [tc for tc in tool_calls if tc["tool"] == "read_file"]
    assert len(read_file_calls) > 0, "Expected read_file to be called"
    
    # Verify it read git.md or git-workflow.md
    git_files = ["wiki/git.md", "wiki/git-workflow.md", "wiki/git-vscode.md"]
    called_paths = [tc["args"]["path"] for tc in read_file_calls]
    assert any(path in called_paths for path in git_files), \
        f"Expected to read one of {git_files}, got {called_paths}"

def test_agent_reads_framework_from_code():
    """Test that agent reads main.py to find the framework."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What Python web framework does this project's backend use?"],
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "FastAPI" in output["answer"]
    assert any(tc["tool"] == "read_file" for tc in output["tool_calls"])

def test_agent_queries_api_for_item_count():
    """Test that agent uses query_api to get item count."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert any(tc["tool"] == "query_api" for tc in output["tool_calls"])
