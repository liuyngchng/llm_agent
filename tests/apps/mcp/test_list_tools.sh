#!/bin/bash
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

curl --noproxy '*' -X POST -s http://localhost:19001/mcp   -H "Content-Type: application/json"   -H "Accept: application/json, text/event-stream"   -H "mcp-session-id: your_session_id"   -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }' | jq


curl --noproxy '*' -X POST -s http://11.10.36.2:19006/mcp   -H "Content-Type: application/json"   -H "Accept: application/json, text/event-stream"   -H "mcp-session-id: your_session_id"   -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }' | jq