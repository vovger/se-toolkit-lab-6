# Agent for Task 2: The Documentation Agent

## Overview
This agent extends the Task 1 implementation with tool-calling capabilities. It can now read files and list directories in the project wiki to answer questions about documentation. The agent implements a full agentic loop that can make multiple tool calls before producing a final answer.

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

## Agentic Loop Implementation
The agent implements a while loop with the following logic:

1. Send user question + tool definitions to LLM
2. Check response for `tool_calls`:
   - If present: execute each tool, append results as `tool` messages, increment counter
   - Maximum 10 iterations (prevents infinite loops)
3. If no tool calls: extract final answer and source reference
4. Output JSON with `answer`, `source`, and full `tool_calls` history

## System Prompt Strategy
The system prompt instructs the LLM to:
- Use `list_files` first to discover available wiki documentation
- Then use `read_file` on relevant files to find answers
- Include source references in format: `wiki/filename.md#section-anchor`
- Ask for clarification if information is insufficient

## Path Security
All file operations are secured by:
- Resolving paths relative to project root
- Using `os.path.abspath` and checking that resolved path stays within project root
- Rejecting any path containing `..` that attempts directory traversal

## Setup
1. Create `.env.agent.secret` file in the project root (use `.env.agent.example` as template)
2. Fill in the required variables:
   ---
   LLM_API_KEY=your-qwen-api-key
   LLM_API_BASE=http://your-vm-ip:42005/v1
   LLM_MODEL=qwen3-coder-plus
   ---
3. Install dependencies: `uv pip install requests python-dotenv`

## Usage
Run the agent with a question as the first argument:
---bash
uv run agent.py "How do I resolve merge conflicts according to the wiki?"
---

## Output Format
The agent outputs a single JSON line to stdout:
---json
{
  "answer": "To resolve merge conflicts: edit the file, keep correct changes, remove conflict markers, then stage and commit.",
  "source": "wiki/git.md#merge-conflict",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki/"},
      "result": "git.md\ngit-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git.md"},
      "result": "# Git\n\n## Merge conflict\n..."
    }
  ]
}
---

- `answer`: the LLM's response (string)
- `source`: reference to the wiki section that answers the question (string)
- `tool_calls`: array of all tool calls made during the agentic loop

All debug and error messages are printed to stderr.

## Error Handling
- Missing environment variables → error message to stderr, exit code 1
- Request timeout (60 seconds) → error to stderr, exit code 1
- Path traversal attempts → error message in tool result
- API errors → error details to stderr, exit code 1
- Max iterations (10) reached → final error message with partial results

## Testing
Two regression tests verify the agent's tool-calling capabilities:
1. Question about merge conflicts → expects `read_file` on `wiki/git.md` in tool calls
2. Question about wiki contents → expects `list_files` on `wiki/` in tool calls
