#!/bin/bash
# =============================================================================
# api_adapter_g — Build & Deploy
#
# Usage:
#   ./deploy/build.sh            # build both binaries + Docker image
#   ./deploy/build.sh run        # build all + deploy container
#   ./deploy/build.sh bin        # build binaries only (Linux + Windows, no Docker)
#
# Outputs:
#   api_adapter_linux_amd64        static ELF — run directly or via Docker
#   api_adapter_windows_amd64.exe  standalone .exe — copy to Windows and run
#   llm_api_adapter_g:1.1          Docker image (ubuntu:24.04)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP="api_adapter_g"
IMAGE="llm_${APP}:1.1"
BIN_LINUX="api_adapter_linux_amd64"
BIN_WIN="api_adapter_windows_amd64.exe"

HOST_CFG_DIR="${PROJECT_DIR}/cfg"
HOST_LOGS_DIR="${PROJECT_DIR}/logs"
CONTAINER="${APP}_app"

MODE="${1:-all}"

# ---- Helper ----
usage() {
    echo "Usage: $0 [all|bin|run]"
    echo "  all   Build Linux + Windows binaries + Docker image (default)"
    echo "  bin   Build both binaries only (no Docker)"
    echo "  run   Build all + deploy container"
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

# ---- Step: deploy (docker run) ----
do_run() {
    echo "=== [deploy] Preparing host directories ==="
    mkdir -p "${HOST_CFG_DIR}" "${HOST_LOGS_DIR}"

    if [ ! -f "${HOST_CFG_DIR}/cfg.yml" ]; then
        if [ -f "cfg.yml.template" ]; then
            cp cfg.yml.template "${HOST_CFG_DIR}/cfg.yml"
            echo "  Created ${HOST_CFG_DIR}/cfg.yml from template — fill in real credentials then restart"
        fi
    else
        echo "  Preserving existing ${HOST_CFG_DIR}/cfg.yml"
    fi

    echo "=== [deploy] Recreating container ==="
    docker stop  "${CONTAINER}" 2>/dev/null || true
    docker rm -f "${CONTAINER}" 2>/dev/null || true
    docker network create llm_net 2>/dev/null || true

    docker run -dit --name "${CONTAINER}" \
      --security-opt seccomp=unconfined \
      --network llm_net \
      -v "${HOST_CFG_DIR}:/opt/app/cfg" \
      -v "${HOST_LOGS_DIR}:/opt/app/logs" \
      -p 16001:16001 \
      -e ADAPTER_CONFIG=/opt/app/cfg/cfg.yml \
      "${IMAGE}"

    echo "  Container started: ${CONTAINER}"
    docker ps -a | grep "${CONTAINER}" --color=always
    echo ""
    docker logs -f "${CONTAINER}"
}

# ---- Main ----
echo "============================================"
echo "  ${APP} — Build & Deploy"
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
        echo "  Run './deploy/build.sh run' to deploy."
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
    run)
        do_clean
        do_binaries
        do_docker
        do_run
        ;;
    *)
        usage
        ;;
esac