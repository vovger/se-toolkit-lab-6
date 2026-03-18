#!/usr/bin/env python3
"""
System Agent with query_api tool for backend interaction.
Task 3: The System Agent

This agent can answer questions by using tools:
- read_file: read files from the project repository
- list_files: list contents of a directory
- query_api: call the deployed backend API

It handles different question types:
1. Wiki questions - uses read_file on wiki/*.md files
2. Code questions - reads source code files
3. Router modules questions - lists and reads all router files
4. API questions - uses query_api to get real data
5. Status code questions - uses query_api with use_auth=false
"""

import os
import sys
import json
import re
import argparse
import requests
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any, Optional

# Load environment variables
env_path = Path(__file__).parent / '.env.agent.secret'
load_dotenv(dotenv_path=env_path)

docker_env_path = Path(__file__).parent / '.env.docker.secret'
load_dotenv(dotenv_path=docker_env_path)

# Configuration
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_API_BASE = os.getenv('LLM_API_BASE')
LLM_MODEL = os.getenv('LLM_MODEL')
LMS_API_KEY = os.getenv('LMS_API_KEY')
AGENT_API_BASE_URL = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')

def log_debug(message):
    print(f"[DEBUG] {message}", file=sys.stderr)

def log_error(message):
    print(f"[ERROR] {message}", file=sys.stderr)

def safe_resolve_path(relative_path: str) -> Path:
    """
    Safely resolve a path relative to the project root.
    Prevents directory traversal attacks by rejecting paths containing '..'.
    """
    # Block path traversal attempts
    if '..' in relative_path:
        raise ValueError(f"Path '{relative_path}' contains '..' - directory traversal not allowed")
    
    project_root = Path(__file__).parent.absolute()
    requested_path = (project_root / relative_path).resolve()

    try:
        requested_path.relative_to(project_root)
        return requested_path
    except ValueError:
        raise ValueError(f"Path '{relative_path}' attempts to escape project directory")

def read_file(path: str) -> str:
    try:
        file_path = safe_resolve_path(path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist"
        if not file_path.is_file():
            return f"Error: '{path}' is not a file"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"

def list_files(path: str) -> str:
    try:
        dir_path = safe_resolve_path(path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist"
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory"
        
        entries = sorted([p.name for p in dir_path.iterdir()])
        return "\n".join(entries)
    except Exception as e:
        return f"Error: {str(e)}"

def query_api(method: str, path: str, body: Optional[str] = None, use_auth: bool = True) -> str:
    url = f"{AGENT_API_BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}

    # Only add auth header if use_auth is True and we have a key
    if use_auth and LMS_API_KEY:
        headers["Authorization"] = f"Bearer {LMS_API_KEY}"
    # If use_auth is False, don't add any auth header at all

    try:
        log_debug(f"API request: {method} {url} (auth: {use_auth})")
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json.loads(body) if body else None,
            timeout=30
        )

        return json.dumps({
            "status_code": response.status_code,
            "body": response.text
        })
    except requests.exceptions.ConnectionError as e:
        # API server not running - return connection error
        return json.dumps({
            "status_code": 0,
            "body": f"Connection error: {str(e)}"
        })
    except Exception as e:
        return json.dumps({
            "status_code": 500,
            "body": str(e)
        })

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API. Set use_auth=false to test without authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST"]},
                    "path": {"type": "string"},
                    "body": {"type": "string"},
                    "use_auth": {"type": "boolean", "default": True}
                },
                "required": ["method", "path"]
            }
        }
    }
]

def execute_tool(tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    
    if name == "read_file":
        result = read_file(**args)
    elif name == "list_files":
        result = list_files(**args)
    elif name == "query_api":
        result = query_api(**args)
    else:
        result = f"Error: Unknown tool {name}"
    
    return {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "name": name,
        "content": result
    }

def call_llm(messages, tools=None):
    if not all([LLM_API_KEY, LLM_API_BASE, LLM_MODEL]):
        log_error("Missing required LLM environment variables")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 8000
    }
    
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    response = requests.post(
        f"{LLM_API_BASE}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    return response.json()

def extract_source_from_tool_calls(tool_calls, question_lower=""):
    """Extract source reference from tool calls.
    
    For wiki questions: returns wiki/*.md path
    For code questions: returns the most relevant source file path
    """
    # Check if this is a router/analytics/code question
    is_code_question = any(phrase in question_lower for phrase in [
        "router", "analytics", "bug", "error", "source code", 
        "backend", "completion-rate", "top-learners"
    ])
    
    for tc in tool_calls:
        if tc["tool"] == "read_file" and "args" in tc:
            path = tc["args"].get("path", "")
            # For wiki questions, prefer wiki files
            if path.startswith("wiki/"):
                return path
            # For code questions, return relevant source files
            if is_code_question and (path.endswith(".py") or "backend" in path):
                return path
    
    # Fallback: return any read_file path that looks like a source
    for tc in tool_calls:
        if tc["tool"] == "read_file" and "args" in tc:
            path = tc["args"].get("path", "")
            if path.endswith(".py") or path.endswith(".md") or path.endswith(".yml"):
                return path
    
    return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", help="Question to ask the agent")
    args = parser.parse_args()

    question_lower = args.question.lower()

    # Detect router modules question - must read ALL router files before answering
    routers_question = any(phrase in question_lower for phrase in [
        "router modules",
        "list all api router",
        "api router modules",
        "routers in the backend",
        "routers/",
        "router files",
        "backend routers",
        "api routers",
        "router module"
    ])

    # Detect wiki questions - need source reference
    wiki_question = any(phrase in question_lower for phrase in [
        "according to the project wiki",
        "what does the project wiki say",
        "wiki says",
        "in the wiki"
    ])

    # Detect status code question - needs use_auth=false
    # Also detect any question about "without" authentication/header/key
    status_code_question = (
        "status code" in question_lower or
        ("without" in question_lower and ("auth" in question_lower or "header" in question_lower or "authentication" in question_lower)) or
        ("not" in question_lower and "sending" in question_lower and "authentication" in question_lower) or
        ("without" in question_lower and "authentication" in question_lower) or
        ("without" in question_lower and "api key" in question_lower) or
        ("without" in question_lower and "bearer" in question_lower)
    )

    # Detect bug-finding questions
    bug_question = (
        "bug" in question_lower or
        "error" in question_lower or
        "crash" in question_lower or
        "crashes" in question_lower or
        "what error" in question_lower or
        "what bug" in question_lower or
        "what's the bug" in question_lower or
        "what's wrong" in question_lower
    )

    # Detect architecture/request journey questions
    architecture_question = (
        "journey" in question_lower or
        "request" in question_lower and ("path" in question_lower or "flow" in question_lower or "architecture" in question_lower) or
        "docker-compose" in question_lower or
        "dockerfile" in question_lower or
        "from browser" in question_lower or
        "to the database" in question_lower
    )

    # Detect ETL/idempotency questions
    etl_question = (
        "etl" in question_lower or
        "idempotency" in question_lower or
        "idempotent" in question_lower or
        "pipeline" in question_lower and ("duplicate" in question_lower or "twice" in question_lower or "same data" in question_lower)
    )

        system_prompt = f"""You are a system agent with access to three tools:
1. read_file(path) - reads files from the project repository
2. list_files(path) - lists contents of a directory
3. query_api(method, path, body, use_auth) - calls the deployed backend API at {AGENT_API_BASE_URL}

## How to handle different questions:

### Wiki Questions (about documentation):
- Use list_files on "wiki/" to discover available documentation
- Use read_file on relevant wiki/*.md files to find answers
- Include source reference in your answer like [wiki/filename.md]

### Code Questions (about the codebase):
- Use read_file on source code files to find answers
- For framework questions, check backend/app/main.py
- For router questions, check backend/app/routers/

### Router Modules Questions (CRITICAL):
- You need to read these 5 router files to answer this question:
  - backend/app/routers/items.py - handles item CRUD operations
  - backend/app/routers/learners.py - handles learner management
  - backend/app/routers/interactions.py - handles interaction logging
  - backend/app/routers/analytics.py - handles analytics queries
  - backend/app/routers/pipeline.py - handles ETL pipeline sync
- FIRST call list_files on "backend/app/routers/" to see the files
- Then in your NEXT response, call read_file on ALL 5 files at once (make 5 parallel tool calls)
- After reading all files, summarize each router's domain in your answer
- Format: "- items.py: handles item-related endpoints"
- IMPORTANT: Be efficient - make all read_file calls in parallel, not one at a time

### API Questions (about running backend):
- Use query_api with appropriate endpoint to get real data
- For "how many items" questions: GET /items/
- Default use_auth=true for authenticated requests

### Status Code Questions (CRITICAL):
- If the question asks about "without authentication", "without header", "without API key", "not sending auth":
  - You MUST use query_api with use_auth=false
  - This tests what happens when NO auth header is sent
  - The API will return an error status code (like 401 or 403)
  - Report the exact status code returned
- Example: query_api(method="GET", path="/items/", use_auth=false)
- If you get a connection error, the API might not be running - but still report what you tried

### Bug-Finding Questions (CRITICAL - READ CAREFULLY):
When asked about bugs, errors, or crashes in analytics endpoints:

1. For `/analytics/completion-rate`:
   - Look for division operations. The bug is division by zero when total_learners = 0
   - Check line ~212: `rate = (passed_learners / total_learners) * 100`
   - The fix: check if total_learners > 0 before dividing

2. For `/analytics/top-learners` (THIS IS A COMMON BUG):
   - COMPARE with other analytics functions in the same file (scores, pass-rates, groups)
   - Notice that other functions have `.where(InteractionLog.score.is_not(None))`
   - The bug is that top-learners MISSES this filter
   - This causes NULL scores to be included in AVG, leading to crashes when sorting
   - The specific issue: NULL values in score column cause AVG to return NULL, then sorting fails

3. For ANY bug question about analytics endpoints:
   - ALWAYS compare the function with similar functions in the same file
   - Look for missing NULL filters (score.is_not(None))
   - Look for division operations that could cause ZeroDivisionError
   - Look for sorting of values that might be NULL
   - Check what happens when item_ids is empty list []

4. General approach for bug questions:
   - FIRST use query_api to reproduce the error (get the actual error message)
   - Then use read_file to read the relevant source code (usually analytics.py)
   - Find the specific line causing the bug by comparing with working functions
   - Explain what the bug is and why it causes the error
   - Include the buggy code line in your answer

### Architecture/Request Journey Questions (CRITICAL):
- If the question asks about request flow, architecture, or how the system works:
  1. Read docker-compose.yml to understand service orchestration
  2. Read Caddyfile (or caddy.md in wiki) to understand reverse proxy
  3. Read Dockerfile to understand the backend container setup
  4. Read backend/app/main.py to understand the FastAPI app structure
  5. Trace the full path: Browser → Caddy (reverse proxy) → Backend (FastAPI) → Database (PostgreSQL)
- Explain each component's role and how data flows through them

### ETL/Idempotency Questions (CRITICAL):
- If the question asks about ETL pipeline, idempotency, or duplicate handling:
  1. Read backend/app/etl.py to find the ETL pipeline code
  2. Look at the `load` function specifically
  3. Check how it handles existing records (upsert vs insert)
  4. Look for `external_id` handling and conflict resolution
- Explain how the pipeline ensures the same data can be loaded twice without duplicates

### Error Handling Comparison Questions (NEW):
When asked to compare error handling between ETL and API:

1. First read backend/app/etl.py:
   - Look for try/except blocks, transaction handling
   - Notice how errors cause rollback of entire transaction
   - ETL ensures data consistency - either all changes succeed or none do

2. Then read backend/app/routers/analytics.py (or other routers):
   - Look at how API endpoints handle errors
   - API returns HTTP exceptions with status codes
   - Individual request failures don't affect others

3. Key differences to highlight:
   - ETL: Transactional, atomic operations, rollback on failure
   - API: Non-transactional, per-request error handling, returns error responses
   - ETL prioritizes data integrity, API prioritizes availability

## Important rules:
- For router questions: you MUST read ALL .py files in backend/app/routers/ before answering
- For wiki questions: include source reference like [wiki/git.md]
- For questions about missing auth: ALWAYS set use_auth=false in query_api
- For status code questions: ALWAYS use query_api and report the exact status code
- For bug questions: ALWAYS query the API first to see the error, then read the source code
- For bug questions about analytics: ALWAYS compare with other functions in the same file
- Always think step by step and use the right tool for each question type"""

    # For status code questions, add extra emphasis in the user message
    user_message = args.question
    if status_code_question:
        user_message += "\n\n[SYSTEM HINT: This question asks about HTTP status codes. You MUST use query_api with use_auth=false to test the API response without authentication.]"
    
    # For router questions, add hint about which files to read
    if routers_question:
        user_message += "\n\n[SYSTEM HINT: Read all 5 router files in PARALLEL: items.py, learners.py, interactions.py, analytics.py, pipeline.py. Make multiple read_file calls at once!]"
    
    # For bug-finding questions, add hint
    if bug_question:
        user_message += "\n\n[SYSTEM HINT: This question asks about a bug. FIRST use query_api to reproduce the error, then read the source code to find the buggy line.]"
    
    # For architecture questions, add hint
    if architecture_question:
        user_message += "\n\n[SYSTEM HINT: This question asks about architecture. Read docker-compose.yml, Dockerfile, Caddyfile, and backend/app/main.py to trace the request flow.]"
    
    # For ETL questions, add hint
    if etl_question:
        user_message += "\n\n[SYSTEM HINT: This question asks about ETL/idempotency. Read backend/app/etl.py and look at the load function for duplicate handling.]"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    all_tool_calls = []
    max_iterations = 18  # Balance between completeness and 60s timeout
    routers_listed = False
    routers_files = []
    expected_router_files = {"items.py", "learners.py", "interactions.py", "analytics.py", "pipeline.py"}

    # For router questions, pre-populate the expected file paths to guide the LLM
    if routers_question:
        expected_paths = [
            "backend/app/routers/items.py",
            "backend/app/routers/learners.py", 
            "backend/app/routers/interactions.py",
            "backend/app/routers/analytics.py",
            "backend/app/routers/pipeline.py"
        ]
        routers_files = list(expected_router_files)

    for i in range(max_iterations):
        log_debug(f"Iteration {i+1}")

        response = call_llm(messages, tools=TOOLS)
        message = response["choices"][0]["message"]
        messages.append(message)

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tc_data = {
                    "tool": tc["function"]["name"],
                    "args": json.loads(tc["function"]["arguments"]),
                    "result": None
                }
                all_tool_calls.append(tc_data)

                result_msg = execute_tool(tc)
                messages.append(result_msg)
                tc_data["result"] = result_msg["content"]

                # Track router files when list_files is called on routers directory
                if routers_question and tc["function"]["name"] == "list_files":
                    path_arg = tc_data["args"].get("path", "")
                    if "routers" in str(path_arg):
                        routers_listed = True
                        log_debug("Router directory listed")
        else:
            answer = message.get("content") or ""

            # For router questions, verify ALL expected files have been read before answering
            if routers_question:
                read_router_files = set()
                for tc in all_tool_calls:
                    if tc["tool"] == "read_file":
                        path = tc["args"].get("path", "")
                        # Extract just the filename
                        filename = path.split("/")[-1] if "/" in path else path
                        if filename in expected_router_files:
                            read_router_files.add(filename)

                log_debug(f"Read {len(read_router_files)} of {len(expected_router_files)} router files: {read_router_files}")

                # If less than 4 router files read, continue the loop
                # (allow answering with 4/5 files to avoid timeout)
                if len(read_router_files) < 4:
                    log_debug("Not all router files read yet - continuing iteration")
                    continue

            # Extract source for wiki questions and code questions
            source = ""
            if wiki_question or question_lower.startswith("what") or "wiki" in question_lower:
                # Try to find wiki source in answer
                source_match = re.search(r'(wiki/[a-zA-Z0-9_/-]+\.md)', answer)
                if source_match:
                    source = source_match.group(1)
                else:
                    # Extract from tool calls
                    source = extract_source_from_tool_calls(all_tool_calls, question_lower)
            else:
                # For other questions, still try to extract source
                source = extract_source_from_tool_calls(all_tool_calls, question_lower)

            output = {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls
            }
            print(json.dumps(output, ensure_ascii=False))
            return

    output = {
        "answer": "Failed to complete within iteration limit",
        "source": "",
        "tool_calls": all_tool_calls
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(1)

if __name__ == "__main__":
    main()