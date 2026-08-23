# api_proxy

A transparent OpenAI API proxy written in Go. It listens on a configurable port and forwards all incoming HTTP requests to an upstream OpenAI-compatible LLM API, injecting the configured API key. No authentication is required on the incoming side.

Can share a single `cfg.yml` with `api_adapter_g` — both access the same upstream, each reads its own port and log file from different field names.

## Key Behaviors

- **No incoming auth** — the proxy does not validate any key on the incoming side.
- **Key injection** — the upstream `llm_api_key` from `cfg.yml` is injected as `Authorization: Bearer <key>` on every forwarded request.
- **Ignores system proxy env vars** — `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, etc. are explicitly ignored when connecting to the upstream (the transport sets `Proxy: nil`).
- **Path preservation** — incoming paths are forwarded as-is, with the upstream base path (e.g. `/v1`) applied exactly once.

## Quick Start

### Build

```bash
# Linux (amd64)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o api_proxy_linux_amd64 .

# Windows (amd64)
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o api_proxy_windows_amd64.exe .

# Or use the helper script
./build.sh
```

### Configure

```bash
cp cfg.yml.template cfg.yml
# Edit cfg.yml with your upstream API URL and key
```

### Run

```bash
./api_proxy_linux_amd64
# Default port: 17001
```

Or with `go run`:

```bash
go run . [port]
```

### Environment Variable

Set `PROXY_CONFIG` to point to an alternative config file path:

```bash
PROXY_CONFIG=/path/to/cfg.yml ./api_proxy_linux_amd64
```

## Usage

Point your OpenAI client at the proxy's listen address. For example, with the OpenAI Python SDK:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://<host>:17001/v1",
    api_key="anything",  # not validated
)
```

Or with `curl`:

```bash
curl -X POST "http://127.0.0.1:17001/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hello"}],"max_tokens":50}'
```

## Shared cfg.yml with api_adapter_g

Both programs can share a single `cfg.yml`. The `api` section is identical; the `sys` section uses different field names:

```yaml
sys:
  name: LLM API Services
  port: 16001                    # api_adapter_g
  proxy_port: 17001              # api_proxy
  log_file: logs/api_adapter.log  # api_adapter_g
  proxy_log_file: logs/api_proxy.log  # api_proxy

api:
  # Both programs use the same upstream
  llm_api_uri: https://api.deepseek.com/v1
  llm_api_key: sk-xxx
  llm_model_name: deepseek-chat
```

Start both together:

```bash
./api_adapter_linux_amd64 &
./api_proxy_linux_amd64 &
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (returns upstream + model info) |
| GET | `/` | Service info |
| ANY | `/*` | Forwarded to the upstream as-is |

## Architecture

```
main.go              — Entry point, reverse proxy, server setup, graceful shutdown
config/config.go     — YAML configuration loading
cfg.yml.template     — Configuration template (shared with api_adapter_g)
build.sh             — Cross-compile helper (Linux + Windows amd64)
```