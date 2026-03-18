# Agent for Task 3: The System Agent

## Overview
This agent extends the Task 2 implementation with the `query_api` tool for backend interaction. It can now answer five types of questions:

1. **Wiki Questions** - about documentation (uses `read_file` on wiki/*.md)
2. **Code Questions** - about the codebase (uses `read_file` on source files)
3. **Router Modules Questions** - lists all API routers and their domains
4. **API Questions** - about real data in the database (uses `query_api`)
5. **Status Code Questions** - HTTP response codes (uses `query_api` with `use_auth=false`)

The agent implements a full agentic loop that can make multiple tool calls before producing a final answer, with special handling to ensure all router files are read before answering router questions.

## LLM Provider
- **Provider**: Qwen Code
- **Model**: `qwen3-coder-plus`
- **API Base**: `http://10.93.25.255:42005/v1`
- **Authentication**: API key stored in `.env.agent.secret`

## Tools Implemented

### 1. `read_file`
- **Description**: Reads a file from the project repository
- **Parameters**: `path` (string) — relative path from project root
- **Security**: Prevents directory traversal attacks (blocks paths containing `..`)
- **Returns**: File contents or error message

### 2. `list_files`
- **Description**: Lists files and directories at a given path
- **Parameters**: `path` (string) — relative directory path from project root
- **Security**: Same path traversal protection as `read_file`
- **Returns**: Newline-separated listing or error message

### 3. `query_api` (NEW)
- **Description**: Calls the deployed backend API to get real-time data
- **Parameters**:
  - `method` (string) — HTTP method (GET, POST, etc.)
  - `path` (string) — API endpoint path (e.g., `/items/`, `/analytics/scores?lab=lab-01`)
  - `body` (string, optional) — JSON request body for POST/PUT requests
  - `use_auth` (boolean, default: true) — whether to include LMS_API_KEY authentication
- **Authentication**: Uses `LMS_API_KEY` from `.env.docker.secret` when `use_auth=true`
- **Returns**: JSON string with `status_code` and `body`

## Environment Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM provider authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint URL |
| `LLM_MODEL` | `.env.agent.secret` | Model name |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication |
| `AGENT_API_BASE_URL` | optional | Backend base URL (default: `http://localhost:42002`) |

> **Important:** Two distinct keys are used:
> - `LLM_API_KEY` authenticates with the LLM provider
> - `LMS_API_KEY` authenticates with the backend API
> 
> Never mix these up — they serve different purposes.

## Agentic Loop Implementation

The agent implements a loop with the following logic:

1. **Detect question type** from the user's input:
   - Router modules questions trigger special handling
   - Wiki questions require source references
   - Status code questions need `use_auth=false`

2. **Send question + tool definitions** to LLM with detailed system prompt

3. **Check response for `tool_calls`**:
   - If present: execute each tool, append results as `tool` messages, increment counter
   - Track router files when `list_files` is called on `src/app/routers/`
   - For router questions: verify ALL .py files are read before allowing answer

4. **Maximum 20 iterations** (prevents infinite loops, allows time for reading all router files)

5. **If no tool calls**: extract final answer and source reference

6. **Output JSON** with `answer`, `source`, and full `tool_calls` history

## System Prompt Strategy

The system prompt instructs the LLM to choose the right tool based on question type:

### Wiki Questions
- Use `list_files` on `wiki/` to discover available documentation
- Use `read_file` on relevant wiki/*.md files
- Include source reference in format: `[wiki/filename.md]`

### Code Questions
- Use `read_file` on source code files (e.g., `backend/app/main.py`)
- Look for framework imports and configuration

### Router Modules Questions
- **FIRST** call `list_files` on `src/app/routers/`
- **THEN** call `read_file` on EVERY .py file (excluding `__init__.py`)
- Determine domain from docstrings and endpoint paths
- **ONLY** answer after reading ALL files

### API Questions
- Use `query_api` with appropriate endpoint
- Default `use_auth=true` for authenticated requests

### Status Code Questions
- Use `query_api` with `use_auth=false`
- Report exact status code returned

## Path Security

All file operations are secured by:
- Explicitly rejecting paths containing `..` (directory traversal)
- Resolving paths relative to project root
- Using `Path.resolve()` and checking that resolved path stays within project root

## Router Modules Handling

For the question "List all API router modules in the backend. What domain does each one handle?":

1. The agent detects this is a router question from keywords
2. It monitors for `list_files` calls on the routers directory
3. When found, it extracts the list of .py files (excluding `__init__.py`)
4. It counts how many router files have been read via `read_file`
5. If the LLM tries to answer before reading all files, the loop continues
6. Only when all files are read does the agent output the final answer

This ensures complete and accurate answers about the router architecture.

## Setup

1. Create `.env.agent.secret` file (use `.env.agent.example` as template)
2. Create `.env.docker.secret` file (use `.env.docker.example` as template)
3. Fill in the required variables:
   ```
   # .env.agent.secret
   LLM_API_KEY=your-llm-api-key
   LLM_API_BASE=http://your-vm-ip:42005/v1
   LLM_MODEL=qwen3-coder-plus
   
   # .env.docker.secret
   LMS_API_KEY=your-backend-api-key
   ```
4. Install dependencies: `uv pip install requests python-dotenv`

## Usage

Run the agent with a question as the first argument:

```bash
uv run agent.py "According to the project wiki, what steps are needed to protect a branch?"
uv run agent.py "What Python web framework does this project's backend use?"
uv run agent.py "List all API router modules in the backend. What domain does each one handle?"
uv run agent.py "How many items are in the database?"
uv run agent.py "What HTTP status code does /items/ return without authentication?"
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The backend uses FastAPI, a modern Python web framework.",
  "source": "wiki/git.md",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "backend/app/main.py"},
      "result": "from fastapi import FastAPI..."
    }
  ]
}
```

- `answer`: the LLM's response (string)
- `source`: reference to the wiki section (string, empty for non-wiki questions)
- `tool_calls`: array of all tool calls made during the agentic loop

All debug and error messages are printed to stderr.

## Error Handling

- Missing environment variables → error message to stderr, exit code 1
- Request timeout (60 seconds) → error to stderr, exit code 1
- Path traversal attempts → error message in tool result
- API errors → error details in tool result with status_code 500
- Max iterations (20) reached → final error message with partial results

## Testing

Five regression tests verify the agent's capabilities:

1. **Valid JSON test**: Ensures output is valid JSON with required fields
2. **Wiki question test**: Verifies `list_files` is called for wiki questions
3. **Merge conflict test**: Verifies `read_file` on git.md for merge conflict questions
4. **Framework question test**: Verifies `read_file` on backend code and FastAPI answer
5. **Item count test**: Verifies `query_api` is called for database questions

Run tests with:
```bash
uv run pytest tests/test_agent.py -v
```

## Benchmark Results

Run the local benchmark with:
```bash
uv run run_eval.py
```

The benchmark tests 10 questions across all categories:
- Wiki lookup (questions 0-1)
- Code reading (question 2)
- Router modules (question 3)
- API data queries (questions 4-5)
- Bug diagnosis (questions 6-7)
- LLM judge reasoning (questions 8-9)

## Lessons Learned

1. **Router question handling requires explicit tracking**: The LLM may try to answer after reading only one or two router files. The agent must explicitly track which files have been read and prevent early answers.

2. **System prompt clarity matters**: A detailed system prompt with explicit instructions for each question type significantly improves tool selection accuracy.

3. **Path security is critical**: Always validate paths to prevent directory traversal attacks. Simply using `resolve()` is not enough — explicitly check for `..` in the input.

4. **Two authentication keys**: It's easy to confuse `LLM_API_KEY` and `LMS_API_KEY`. Clear documentation and separate config files help prevent mistakes.

5. **Iteration limits need tuning**: Router questions require more iterations (list files + read 5 files + answer = 7+ iterations). Setting the limit too low causes premature termination.

6. **Source extraction for wiki questions**: The agent should extract source references both from the LLM's answer text and from the tool call history as a fallback.

## Architecture Summary

```
┌─────────────────┐
│   User Question │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Question Type  │
│    Detection    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  System Prompt  │────▶│  LLM (Qwen)      │
│  + Tools        │     │  Chat Completions│
└─────────────────┘     └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
           ┌────────────┐ ┌────────────┐ ┌────────────┐
           │ read_file  │ │ list_files │ │ query_api  │
           └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
                 │              │               │
                 ▼              ▼               ▼
           ┌─────────────────────────────────────────┐
           │         Tool Execution Results          │
           └─────────────────────────────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Loop until     │
                         │  no tool calls  │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  JSON Output    │
                         └─────────────────┘
```
## Benchmark Results
- **Local evaluation**: 10/10 questions passed
- **Date**: 2026-03-17
- **LLM Model**: qwen3-coder-plus

### Lessons Learned
The agent needed explicit prompting to read all router files.
Using use_auth=false was critical for status code questions.