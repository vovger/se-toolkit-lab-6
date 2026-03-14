# Agent for Task 1: Call an LLM from Code

## Overview
This agent is a simple CLI tool that sends a question to an LLM and returns a structured JSON response. It serves as the foundation for more complex agents in Tasks 2-3.

## LLM Provider
- **Provider**: Qwen Code
- **Model**: `qwen3-coder-plus`
- **API Base**: `http://10.93.25.255:42005/v1`
- **Authentication**: API key stored in `.env.agent.secret`

## Setup
1. Create `.env.agent.secret` file in the project root (use `.env.agent.example` as template)
2. Fill in the required variables:
   ```
   LLM_API_KEY=your-qwen-api-key
   LLM_API_BASE=http://your-vm-ip:42005/v1
   LLM_MODEL=qwen3-coder-plus
   ```
3. Install dependencies: `uv pip install requests python-dotenv`

## Usage
Run the agent with a question as the first argument:
```bash
uv run agent.py "What is REST?"
```

## Output Format
The agent outputs a single JSON line to stdout:
```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```
- `answer`: the LLM's response (string)
- `tool_calls`: empty array (reserved for Task 2)

All debug and error messages are printed to stderr.

## Error Handling
- Missing environment variables → error message to stderr, exit code 1
- Request timeout (60 seconds) → error to stderr, exit code 1
- API errors → error details to stderr, exit code 1
