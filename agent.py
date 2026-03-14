#!/usr/bin/env python3
"""
Agent that calls LLM and returns structured JSON response.
Task 1: Call an LLM from Code
"""

import os
import sys
import json
import argparse
import requests
from dotenv import load_dotenv
from pathlib import Path

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

def call_llm(question):
    """Send question to LLM and return answer text."""
    if not all([LLM_API_KEY, LLM_API_BASE, LLM_MODEL]):
        log_error("Missing required environment variables. Check .env.agent.secret")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
            {"role": "user", "content": question}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }

    try:
        log_debug(f"Sending request to {LLM_API_BASE}/chat/completions")
        response = requests.post(
            f"{LLM_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract answer from response
        answer = result['choices'][0]['message']['content']
        return answer.strip()

    except requests.exceptions.Timeout:
        log_error("Request timed out after 60 seconds")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        log_error(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response:
            log_error(f"Response body: {e.response.text}")
        sys.exit(1)
    except (KeyError, json.JSONDecodeError) as e:
        log_error(f"Failed to parse LLM response: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Call LLM with a question")
    parser.add_argument("question", help="Question to ask the LLM")
    args = parser.parse_args()

    answer = call_llm(args.question)
    
    # Output JSON to stdout
    output = {
        "answer": answer,
        "tool_calls": []  # Empty for Task 1
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
