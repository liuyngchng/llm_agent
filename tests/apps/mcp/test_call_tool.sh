#!/bin/bash
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

curl -X POST -s http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: your_session_id" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_desktop_files",
      "arguments": {}
    }
  }' | jq