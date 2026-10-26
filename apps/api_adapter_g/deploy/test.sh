#!/bin/bash
# =============================================================================
# api_adapter_g — API smoke test
#
# Usage:
#   ./deploy/test.sh              # auto-detect port from cfg/cfg.yml
#   ./deploy/test.sh 8080         # custom port
#   ./deploy/test.sh 192.168.1.1  # remote host (auto-detect port)
#   ./deploy/test.sh 192.168.1.1:8080  # remote host:port
#
# Reads cfg/cfg.yml to get the API key, model name, and port.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="16001"

# ---- Read config from cfg/cfg.yml ----
CFG_FILE="${PROJECT_DIR}/cfg/cfg.yml"
API_KEY=""
MODEL_NAME=""
CFG_PORT=""

if [ -f "$CFG_FILE" ]; then
    API_KEY=$(grep -E '^\s*llm_api_key:' "$CFG_FILE" | head -1 | sed 's/.*:\s*//' | xargs)
    MODEL_NAME=$(grep -E '^\s*llm_model_name:' "$CFG_FILE" | head -1 | sed 's/.*:\s*//' | xargs)
    CFG_PORT=$(grep -E '^\s*port:' "$CFG_FILE" | head -1 | sed 's/.*:\s*//' | xargs)
fi

API_KEY="${API_KEY:-sk-test-key}"
MODEL_NAME="${MODEL_NAME:-deepseek-v4-pro}"
DEFAULT_PORT="${CFG_PORT:-${DEFAULT_PORT}}"

# ---- Resolve HOST:PORT from CLI arg ----
ARG="${1:-}"
if [ -z "$ARG" ]; then
    HOST="$DEFAULT_HOST"
    PORT="$DEFAULT_PORT"
elif [[ "$ARG" =~ ^[0-9]+$ ]]; then
    HOST="$DEFAULT_HOST"
    PORT="$ARG"
elif [[ "$ARG" =~ : ]]; then
    HOST="${ARG%:*}"
    PORT="${ARG##*:}"
else
    HOST="$ARG"
    PORT="$DEFAULT_PORT"
fi

BASE_URL="http://${HOST}:${PORT}"

# ---- Colours ----
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS="${GREEN}PASS${NC}"
FAIL="${RED}FAIL${NC}"

# =========================================================================
echo "============================================"
echo "  api_adapter_g — API Smoke Test"
echo "  Target: ${BASE_URL}"
echo "  Model : ${MODEL_NAME}"
echo "============================================"
echo ""

# ---- POST /v1/messages ----
echo "POST /v1/messages ..."

BODY=$(curl -s -w "\n%{http_code}" \
    -X POST "${BASE_URL}/v1/messages" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
  "model": "'"${MODEL_NAME}"'",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "max_tokens": 50
}')
HTTP_CODE=$(echo "$BODY" | tail -1)
RESP=$(echo "$BODY" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    # Verify Anthropic response format
    if echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('type')=='message' and 'content' in d" 2>/dev/null; then
        echo -e "  ${PASS}  HTTP ${HTTP_CODE}, Anthropic response ok"
        echo ""
        echo "Response:"
        echo "$RESP" | python3 -m json.tool --ensure-ascii=false 2>/dev/null || echo "$RESP"
    else
        echo -e "  ${FAIL}  HTTP ${HTTP_CODE}, not a valid Anthropic response"
        echo "  ${RESP}"
        exit 1
    fi
else
    echo -e "  ${FAIL}  HTTP ${HTTP_CODE}"
    echo "  ${RESP}"
    exit 1
fi
