#!/bin/bash
# =============================================================================
# Build: api_adapter_go — standalone Windows .exe (no runtime DLLs needed)
# Output: deploy/api_adapter_go_windows_amd64.exe
#
# CGO_ENABLED=0 produces a pure Go binary — no libc, no mingw, no vcredist.
# Runs on Windows 7+ / Server 2008 R2+ as-is.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"          # api_adapter_go/
OUTPUT="${APP_DIR}/deploy/api_adapter_g_windows_amd64.exe"

cd "$APP_DIR"

# 设置 Go 代理，便于下载相关组件
go env -w GOPROXY=https://goproxy.cn,direct

echo "=== Building static Windows .exe ==="
echo "  Source : $APP_DIR"
echo "  Output : $OUTPUT"
echo "  Target : windows/amd64, CGO_ENABLED=0"

CGO_ENABLED=0 \
GOOS=windows \
GOARCH=amd64 \
  go build \
    -trimpath \
    -ldflags="-s -w -extldflags '-static'" \
    -o "$OUTPUT" \
    .

if [ $? -ne 0 ]; then
    echo "[FAIL] Build failed."
    exit 1
fi

echo ""
echo "=== Verifying binary ==="
file "$OUTPUT"
echo ""
ls -lh "$OUTPUT"
echo ""
echo "[OK] Windows .exe ready: $OUTPUT"
echo ""
echo "  Deploy it alongside cfg.yml and run:"
echo "    api_adapter_g_windows_amd64.exe [port]"
