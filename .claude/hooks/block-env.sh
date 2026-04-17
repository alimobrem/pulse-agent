#!/bin/bash
# Block edits to .env files
FILE=$(jq -r '.tool_input.file_path // empty')
if echo "$FILE" | grep -q '\.env'; then
  echo '{"decision":"block","reason":"BLOCKED: .env files should not be edited directly. Use environment variables or settings."}'
fi
