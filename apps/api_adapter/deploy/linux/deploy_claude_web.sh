#!/bin/bash
# 需要在容器内启动 api_adaptor,
# /opt/workspace/llm_agent
# python -m apps.api_adapter.app &
docker run -dit \
	  --name my_claude_code \
	  --rm \
	  -v /data/claude_code:/opt/workspace \
	  -e NODE_TLS_REJECT_UNAUTHORIZED=0 \
	  -e ANTHROPIC_BASE_URL=http://127.0.0.1:16001 \
	  -e ANTHROPIC_AUTH_TOKEN=sk-*** \
	  -e API_TIMEOUT_MS=600000 \
	  -e ANTHROPIC_MODEL=deepseek-chat \
	  -e ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat \
	  -e CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
	  -e CLAUDE_CODE_ATTRIBUTION_HEADER=0 \
    -e TZ=Asia/Shanghai \
    -e LANG=C.UTF-8 \
    -e LC_ALL=C.UTF-8 \
	  -p 19004:8765 \
	  my_claude_code:1.0 \
	  /opt/llm_py_env/bin/claude-web --host 0.0.0.0