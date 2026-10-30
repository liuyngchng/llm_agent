#!/bin/bash
# =============================================================================
# api_adapter_g — Deploy (docker run only, no build)
#
# Usage:
#   ./deploy/deploy.sh
#
# Prerequisites:
#   Docker image llm_api_adapter_g:1.1 must already exist (built via ./deploy/build.sh)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP="api_adapter_g"
IMAGE="llm_${APP}:1.1"
CONTAINER="${APP}_app"

HOST_CFG_DIR="${PROJECT_DIR}/cfg"
HOST_LOGS_DIR="${PROJECT_DIR}/logs"

echo "============================================"
echo "  ${APP} — Deploy"
echo "  Project : ${PROJECT_DIR}"
echo "============================================"
echo ""

# 检查 Docker 镜像是否存在
if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE}$"; then
    echo "错误：Docker 镜像 ${IMAGE} 不存在"
    echo "请先执行 ./deploy/build.sh 构建镜像"
    exit 1
fi

echo "=== [deploy] Preparing host directories ==="
mkdir -p "${HOST_CFG_DIR}" "${HOST_LOGS_DIR}"

# 检测配置文件，缺少则报错退出，不自动拷贝
if [ ! -f "${HOST_CFG_DIR}/cfg.yml" ]; then
    echo "错误：配置文件 ${HOST_CFG_DIR}/cfg.yml 不存在"
    echo "请参考 cfg.yml.template 手动创建该文件并填写 API 密钥后重新部署"
    exit 1
fi
# 从 cfg.yml 读取端口（默认 16001）
PORT=$(grep -E '^\s*port:' "${HOST_CFG_DIR}/cfg.yml" | head -1 | sed 's/.*:\s*//' | xargs)
PORT="${PORT:-16001}"
echo "  端口: ${PORT}"

echo "=== [deploy] 停止并删除旧容器 ==="
docker stop  "${CONTAINER}" 2>/dev/null || true
docker rm -f "${CONTAINER}" 2>/dev/null || true

echo "=== [deploy] 创建 docker 网络 ==="
docker network create llm_net 2>/dev/null || true

echo "=== [deploy] 启动容器 ==="
docker run -dit --name "${CONTAINER}" \
  --security-opt seccomp=unconfined \
  --network llm_net \
  -v "${HOST_CFG_DIR}:/opt/app/cfg" \
  -v "${HOST_LOGS_DIR}:/opt/app/logs" \
  -p ${PORT}:${PORT} \
  -e TZ=Asia/Shanghai \
  -e ADAPTER_CONFIG=/opt/app/cfg/cfg.yml \
  "${IMAGE}"

echo "容器 ${CONTAINER} 已启动"
echo ""
echo "=== [deploy] llm_net 容器间互访地址 ==="
echo -e "  同网络其他容器可通过以下地址访问本容器：\033[31mhttp://${CONTAINER}:${PORT}\033[0m"
echo ""
docker ps -a | grep "${CONTAINER}" --color=always
echo ""
echo "部署完成"
docker logs -f "${CONTAINER}"