#!/usr/bin/env python3
"""
Documentation Agent with tools (read_file, list_files).
Task 2: The Documentation Agent
"""

import os
import sys
import json
import re
import argparse
import requests
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Any

# Load environment variables from .env.agent.secret
env_path = Path(__file__).parent / '.env.agent.secret'
load_dotenv(dotenv_path=env_path)

# Configuration
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_API_BASE = os.getenv('LLM_API_BASE')
LLM_MODEL = os.getenv('LLM_MODEL')

def log_debug(message):
    """Print debug information to stderr."""
    print(f"[DEBUG] {message}", file=sys.stderr)

def log_error(message):
    """Print error information to stderr."""
    print(f"[ERROR] {message}", file=sys.stderr)

def safe_resolve_path(relative_path: str) -> Path:
    """Resolve path safely to prevent directory traversal."""
    project_root = Path(__file__).parent.absolute()
    requested_path = (project_root / relative_path).resolve()
    
    # Check if the resolved path is within project root
    try:
        requested_path.relative_to(project_root)
        return requested_path
    except ValueError:
        raise ValueError(f"Path '{relative_path}' attempts to escape project directory")

def read_file(path: str) -> str:
    """Read a file from the project repository."""
    try:
        file_path = safe_resolve_path(path)
        if not file_path.exists():
            return f"Error: File '{path}' does not exist"
        if not file_path.is_file():
            return f"Error: '{path}' is not a file"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def list_files(path: str) -> str:
    """List files and directories at a given path."""
    try:
        dir_path = safe_resolve_path(path)
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist"
        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory"
        
        entries = sorted([p.name for p in dir_path.iterdir()])
        return "\n".join(entries)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"

# Tool definitions for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository to access documentation content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path to discover available documentation",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki/')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

def execute_tool(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call and return the result in OpenAI format."""
    tool_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    
    if tool_name == "read_file":
        result = read_file(**arguments)
    elif tool_name == "list_files":
        result = list_files(**arguments)
    else:
        result = f"Error: Unknown tool '{tool_name}'"
    
    return {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "name": tool_name,
        "content": result
    }

def call_llm(messages, tools=None, tool_choice=None):
    """Send messages to LLM with optional tools."""
    if not all([LLM_API_KEY, LLM_API_BASE, LLM_MODEL]):
        log_error("Missing required environment variables. Check .env.agent.secret")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"

    try:
        log_debug(f"Sending request to {LLM_API_BASE}/chat/completions")
        response = requests.post(
            f"{LLM_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        log_error("Request timed out after 60 seconds")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        log_error(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response:
            log_error(f"Response body: {e.response.text}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Documentation agent with tools")
    parser.add_argument("question", help="Question to ask about the project documentation")
    args = parser.parse_args()

    # System prompt that instructs the LLM how to use tools
    system_prompt = """You are a documentation assistant for a software engineering toolkit project. 
You have access to two tools:
- list_files: to see what files are available in the wiki directory
- read_file: to read the contents of wiki files

Always use list_files first to discover available documentation, then read_file to find answers.
When you find the answer, include the source reference in format: wiki/filename.md#section-anchor.
If you need more information, use the tools again. Be concise but thorough."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": args.question}
    ]
    
    all_tool_calls = []
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        log_debug(f"Agent iteration {iteration}")
        
        response = call_llm(messages, tools=TOOLS)
        choice = response["choices"][0]
        message = choice["message"]
        
        # Add assistant message to history
        messages.append(message)
        
        # Check for tool calls
        if message.get("tool_calls"):
            tool_calls = message["tool_calls"]
            log_debug(f"Executing {len(tool_calls)} tool calls")
            
            # Store tool calls for final output
            for tc in tool_calls:
                all_tool_calls.append({
                    "tool": tc["function"]["name"],
                    "args": json.loads(tc["function"]["arguments"]),
                    "result": None  # Will be filled after execution
                })
            
            # Execute each tool
            for tc in tool_calls:
                result_msg = execute_tool(tc)
                messages.append(result_msg)
                
                # Update stored tool call with result
                for stored_tc in all_tool_calls:
                    if stored_tc["tool"] == tc["function"]["name"] and stored_tc["result"] is None:
                        stored_tc["result"] = result_msg["content"]
                        break
        else:
            # No tool calls - this is the final answer
            answer = message["content"]
            
            # Try to extract source from answer (simple heuristic)
            source = ""
            source_match = re.search(r'(wiki/[a-zA-Z0-9_-]+\.md(?:#[a-zA-Z0-9_-]+)?)', answer)
            if source_match:
                source = source_match.group(1)
            
            # Output JSON
            output = {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls
            }
            print(json.dumps(output, ensure_ascii=False))
            return
    
    # If we hit max iterations
    log_error(f"Reached maximum iterations ({max_iterations}) without final answer")
    output = {
        "answer": "I couldn't find a complete answer within the allowed iterations.",
        "source": "",
        "tool_calls": all_tool_calls
    }
    print(json.dumps(output, ensure_ascii=False))
    sys.exit(1)

if __name__ == "__main__":
    main()
