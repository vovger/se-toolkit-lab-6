# Task 2: The Documentation Agent - Implementation Plan

## 1. Tool Schemas
I will implement two tools using OpenAI-compatible function calling format:

### read_file
- **Description**: Read a file from the project repository to access documentation content.
- **Parameters**: 
  ```json
  {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the file from project root (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
  ```
- **Returns**: File contents as string, or error message if file doesn't exist or is outside project.

### list_files
- **Description**: List files and directories at a given path to discover available documentation.
- **Parameters**:
  ```json
  {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki/')"
      }
    },
    "required": ["path"]
  }
  ```
- **Returns**: Newline-separated listing of entries, or error message if path is invalid.

## 2. Agentic Loop Implementation
The main loop in `agent.py` will:

1. Send initial user question + tool definitions to LLM
2. Check response for `tool_calls`:
   - If present: execute each tool, append results as `tool` role messages, increment counter
   - If counter < 10: repeat from step 1
   - If counter >= 10: break and use current answer
3. If no tool calls: extract final answer and source
4. Output JSON with fields: `answer`, `source`, `tool_calls` (array of all calls made)

The loop will be implemented as a `while` loop with careful error handling for tool execution failures.

## 3. Path Security
To prevent directory traversal attacks:

- Get absolute project root path using `os.path.abspath(os.path.dirname(__file__))`
- For any requested path, construct absolute path: `os.path.abspath(os.path.join(project_root, path))`
- Verify that the resolved path starts with `project_root` using `os.path.commonpath`
- Reject any path that attempts to escape project directory
- Use `os.path.exists` and `os.path.isfile`/`os.path.isdir` for validation

## 4. System Prompt Strategy
The system prompt will instruct the LLM to:

- Use `list_files` first to discover available wiki files
- Then use `read_file` on relevant files to find answers
- When answering, include source reference in format: `wiki/filename.md#section-anchor`
- Ask for clarification if information is insufficient

## 5. Testing Strategy
I will add two new regression tests in `tests/test_agent.py`:

### Test 1: Merge conflict resolution
- Input: "How do you resolve a merge conflict?"
- Expected: `tool_calls` contains `read_file` with `wiki/git-workflow.md`
- Expected: `source` field contains reference to merge conflict section

### Test 2: Wiki file discovery
- Input: "What files are in the wiki?"
- Expected: `tool_calls` contains `list_files` with path "wiki/"
- Expected: `answer` contains list of files

Both tests will verify:
- Valid JSON output structure
- Required fields present
- Tool calls properly recorded
- No path traversal attempts succeed

## 6. Documentation Updates
`AGENT.md` will be updated with:

- Description of new tools and their schemas
- Explanation of the agentic loop
- System prompt strategy
- Security considerations for file access
