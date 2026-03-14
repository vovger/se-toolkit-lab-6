# Task 1: Call an LLM from Code

## 1. LLM Provider and Model
- **Provider**: Qwen Code (deployed on VM)
- **Model**: `qwen3-coder-plus`
- **API Base**: `http://<VM-IP>:42005/v1` (from `.env.agent.secret`)
- **Authentication**: API key from `.env.agent.secret`

## 2. Implementation Plan

### 2.1. Project Structure
- `agent.py` — main agent script
- `.env.agent.secret` — environment variables file (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
- `plans/task-1.md` — this plan
- `AGENT.md` — agent documentation
- `tests/` — test directory

### 2.2. Agent Implementation (`agent.py`)
Will use:
- `python-dotenv` to load environment variables
- `requests` for HTTP calls to LLM API
- `argparse` for command-line argument handling
- `sys.stdout` for JSON output, `sys.stderr` for logs

### 2.3. Algorithm
1. Load variables from `.env.agent.secret`
2. Get question from command-line arguments
3. Create minimal system prompt (e.g., "You are a helpful assistant")
4. Send POST request to LLM API
5. Parse response and extract answer text
6. Output JSON to stdout: `{"answer": "...", "tool_calls": []}`
7. On errors — print to stderr and exit with code 1

### 2.4. Error Handling
- Request timeout — 60 seconds (as required)
- Handle API unavailability
- Handle malformed JSON from LLM
- All errors go to stderr

## 3. Testing Strategy
- Create one regression test in `tests/test_agent.py`
- Test runs `agent.py` as a subprocess with a test question
- Verify stdout contains valid JSON with `answer` and `tool_calls` fields
- Use `pytest` framework

## 4. Documentation
- `AGENT.md` will describe:
  - Environment setup (`.env.agent.secret`)
  - How to run the agent
  - Which LLM provider is used
  - Output format
