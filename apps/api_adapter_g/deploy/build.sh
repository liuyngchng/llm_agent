#!/bin/bash
# =============================================================================
# api_adapter_g — Build
#
# Usage:
#   ./deploy/build.sh            # build both binaries + Docker image
#   ./deploy/build.sh bin        # build binaries only (Linux + Windows, no Docker)
#
# Outputs:
#   api_adapter_linux_amd64        static ELF — run directly or via Docker
#   api_adapter_windows_amd64.exe  standalone .exe — copy to Windows and run
#   llm_api_adapter_g:1.1          Docker image (ubuntu:24.04)
#
# To deploy the Docker container, use:  ./deploy/deploy.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP="api_adapter_g"
IMAGE="llm_${APP}:1.1"
BIN_LINUX="api_adapter_linux_amd64"
BIN_WIN="api_adapter_windows_amd64.exe"

MODE="${1:-all}"

# ---- Helper ----
usage() {
    echo "Usage: $0 [all|bin]"
    echo "  all   Build Linux + Windows binaries + Docker image (default)"
    echo "  bin   Build both binaries only (no Docker)"
    exit 1
}

# ---- Step: clean ----
do_clean() {
    echo "=== [clean] Removing previous binaries ==="
    rm -f "${BIN_LINUX}" "${BIN_WIN}"
    echo "  Done."
}

# ---- Step: build both binaries ----
do_binaries() {
    go env -w GOPROXY=https://goproxy.cn,direct

    # --- Linux ---
    echo "=== [1/2] Building static Linux ELF ==="
    CGO_ENABLED=0 \
    GOOS=linux \
    GOARCH=amd64 \
      go build \
        -trimpath \
        -ldflags="-s -w -extldflags '-static'" \
        -o "${BIN_LINUX}" \
        .

    echo "  Binary: ${BIN_LINUX}"
    file "${BIN_LINUX}"
    readelf -d "${BIN_LINUX}" 2>/dev/null | grep NEEDED \
        && echo "  ⚠ WARNING: has dynamic deps" \
        || echo "  ✓ Fully static"
    ls -lh "${BIN_LINUX}"

    # --- Windows ---
    echo ""
    echo "=== [2/2] Building Windows .exe ==="
    CGO_ENABLED=0 \
    GOOS=windows \
    GOARCH=amd64 \
      go build \
        -trimpath \
        -ldflags="-s -w -extldflags '-static'" \
        -o "${BIN_WIN}" \
        .

    echo "  Binary: ${BIN_WIN}"
    file "${BIN_WIN}"
    ls -lh "${BIN_WIN}"

    echo ""
    echo "  Deploy (no Docker needed):"
    echo "    Linux  : ./${BIN_LINUX} [-p PORT]"
    echo "    Windows: ${BIN_WIN} [PORT]"
}

# ---- Step: Docker image ----
do_docker() {
    echo "=== [docker] Building Docker image ==="
    docker build --rm -f Dockerfile . -t "${IMAGE}"
    echo "  Image: ${IMAGE}"
    docker images | grep "${IMAGE}" --color=always || true
}

# ---- Main ----
echo "============================================"
echo "  ${APP} — Build"
echo "  Project : ${PROJECT_DIR}"
echo "============================================"
echo ""

case "${MODE}" in
    all)
        do_clean
        do_binaries
        do_docker
        echo ""
        echo "============================================"
        echo "  Done."
        echo "    ELF    : ./${BIN_LINUX}"
        echo "    EXE    : ./${BIN_WIN}"
        echo "    Image  : ${IMAGE}"
        echo "  Run './deploy/deploy.sh' to deploy."
        echo "============================================"
        ;;
    bin)
        do_clean
        do_binaries
        echo ""
        echo "============================================"
        echo "  Binaries ready:"
        echo "    Linux  : ./${BIN_LINUX}"
        echo "    Windows: ./${BIN_WIN}"
        echo "============================================"
        ;;
    *)
        usage
        ;;
esac