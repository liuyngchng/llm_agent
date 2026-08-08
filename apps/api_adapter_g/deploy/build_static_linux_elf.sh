#!/bin/bash
# =============================================================================
# Build: api_adapter_go — fully static Linux ELF binary
# Output: deploy/api_adapter_go_linux_amd64
#
# CGO_ENABLED=0 produces a binary with no libc dependency — runs on any
# Linux kernel 2.6.32+ (any modern distro, Alpine, scratch containers).
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"          # api_adapter_go/
OUTPUT="${APP_DIR}/deploy/api_adapter_g_linux_amd64"

cd "$APP_DIR"

# 设置 Go 代理，便于下载相关组件
go env -w GOPROXY=https://goproxy.cn,direct

echo "=== Building static Linux ELF ==="
echo "  Source : $APP_DIR"
echo "  Output : $OUTPUT"
echo "  Target : linux/amd64, CGO_ENABLED=0"

CGO_ENABLED=0 \
GOOS=linux \
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

# Verify it's really static
echo ""
echo "=== Verifying binary ==="
file "$OUTPUT"
echo ""
echo "Dynamic symbol check (expect empty):"
readelf -d "$OUTPUT" 2>/dev/null | grep NEEDED || echo "  ✓ No shared library dependencies — fully static"
echo ""
ls -lh "$OUTPUT"
echo ""
echo "[OK] Static Linux binary ready: $OUTPUT"
