#!/bin/bash
# Auto-format Python files after edit
FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
if echo "$FILE" | grep -qE '\.py$'; then
  python3 -m ruff format --quiet "$FILE" 2>/dev/null
fi
exit 0
