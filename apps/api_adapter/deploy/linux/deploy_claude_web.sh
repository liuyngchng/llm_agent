#!/bin/bash
# 需要在容器内启动 api_adaptor,
# cd /opt/claude_code/llm_agent
# python -m apps.api_adapter.app &
# 环境变量中配置 LOCAL_LLM_AUTH_TOKEN
APP="claude_code_web"
CONTAINER="claude_code_web"
AUTH_TOKEN=${LOCAL_LLM_API_KEY}
# 校验 AUTH_TOKEN 是否为空
if [ -z "${AUTH_TOKEN}" ]; then
    echo "错误: 环境变量 LOCAL_LLM_API_KEY 未设置或为空"
    echo "请先设置环境变量: export LOCAL_LLM_API_KEY='your_token_here'"
    echo "或者: LOCAL_LLM_API_KEY='your_token_here' ./deploy_claude_web.sh"
    exit 1
fi
echo "开始部署 ${APP} 服务"
docker stop ${CONTAINER}
echo "正在删除 ${APP} 服务"
docker rm ${CONTAINER}
echo "开始创建 ${CONTAINER} 容器"
WORKSPACE="/opt/workspace"
HOST_WORKSPACE="/data/claude_code/workspace"
echo "workspace in container, ${WORKSPACE}, on host, ${HOST_WORKSPACE}"
docker run -dit \
	--name ${CONTAINER} \
	--rm \
	--security-opt seccomp=unconfined \
  --network llm_net \
  -v ${HOST_WORKSPACE}:${WORKSPACE} \
	-w ${WORKSPACE} \
	-e NODE_TLS_REJECT_UNAUTHORIZED=0 \
	-e ANTHROPIC_BASE_URL=http://api_adapter_app:19000 \
	-e ANTHROPIC_AUTH_TOKEN=${AUTH_TOKEN} \
	-e API_TIMEOUT_MS=600000 \
	-e ANTHROPIC_MODEL=deepseek-chat \
	-e ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat \
	-e CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
	-e CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
  	-e TZ=Asia/Shanghai \
  	-e LANG=C.UTF-8 \
  	-e LC_ALL=C.UTF-8 \
	-p 19004:3001 \
	my_claude_code:1.0 \
	/root/.nvm/versions/node/v22.22.3/bin/cloudcli

echo "容器 ${CONTAINER} 已启动"
docker ps -a  | grep ${CONTAINER} --color=always
echo "部署完成"
docker logs -f ${CONTAINER}