# Task 3: The System Agent - Implementation Plan

## 1. New Tool: `query_api`

### Schema Definition
- **Name**: `query_api`
- **Description**: Make HTTP requests to the deployed backend API to get real system data
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "enum": ["GET", "POST", "PUT", "DELETE"],
        "description": "HTTP method for the request"
      },
      "path": {
        "type": "string",
        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate?lab=lab-01')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT requests"
      }
    },
    "required": ["method", "path"]
  }
  ```
- **Returns**: JSON string with `status_code` and `body`

### Authentication
- Use `LMS_API_KEY` from environment variables (from `.env.docker.secret`)
- Add to request headers: `Authorization: Bearer {LMS_API_KEY}`

### Base URL
- Read `AGENT_API_BASE_URL` from environment
- Default to `http://localhost:42002` if not set

## 2. Environment Variables
| Variable | Source | Purpose |
|----------|--------|---------|
| `LLM_API_KEY` | `.env.agent.secret` | LLM authentication |
| `LLM_API_BASE` | `.env.agent.secret` | LLM API endpoint |
| `LLM_MODEL` | `.env.agent.secret` | Model name |
| `LMS_API_KEY` | `.env.docker.secret` | Backend API authentication |
| `AGENT_API_BASE_URL` | optional | Backend base URL (default: localhost:42002) |

## 3. System Prompt Updates
The prompt will be extended to help the LLM choose the right tool:
- **Wiki questions** (setup, config) → `read_file` on wiki/
- **Code questions** (framework, structure) → `read_file` on source files
- **System facts** (ports, status codes) → `read_file` on code or `query_api`
- **Data questions** (item count, analytics) → `query_api` first
- **Bug diagnosis** → `query_api` to see error, then `read_file` to find cause

## 4. Benchmark Strategy
1. Run benchmark first to see baseline: `uv run run_eval.py`
2. Fix questions one by one in order:
   - Wiki questions (0-1) → should already work from Task 2
   - Code reading (2-3) → should work
   - Simple API calls (4-5) → implement `query_api`
   - Bug diagnosis (6-7) → need tool chaining
   - LLM judge questions (8-9) → need good prompting
3. Document failures and fixes in this plan

## 5. Testing Strategy
Two new tests:
1. **Code reading test**: "What framework does the backend use?" → expects `read_file` on backend code
2. **API test**: "How many items are in the database?" → expects `query_api` with GET /items/

## 6. Documentation Updates
`AGENT.md` will include:
- `query_api` tool description and schema
- Authentication setup
- Decision tree for tool selection
- Benchmark results and lessons learned (200+ words)
