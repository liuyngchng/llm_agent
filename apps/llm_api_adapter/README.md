在 Claude Code 中使用时，设置环境变量   
ANTHROPIC_BASE_URL=http://127.0.0.1:16001  
ANTHROPIC_API_KEY=<cfg.yml 中的 llm_api_key>



cat /etc/profile 

```sh
export ANTHROPIC_BASE_URL=http://127.0.0.1:16001
export ANTHROPIC_AUTH_TOKEN=sk-8rfe*****e
export API_TIMEOUT_MS=600000
export ANTHROPIC_MODEL=deepseek-chat
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat
export CLAUDE_CODE_DISABLE_NONSENSENTIAL_TRAFFIC=1
```

