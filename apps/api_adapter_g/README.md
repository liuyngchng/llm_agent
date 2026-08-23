# api_adapter_go

OpenAI-to-Anthropic API protocol adapter written in Go. Accepts Anthropic Messages API requests and forwards them to an OpenAI-compatible upstream LLM API.

## Quick Start

### Build

```bash
# Linux (amd64)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o api_adapter_linux_amd64 .

# Windows (amd64)
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o api_adapter_windows_amd64.exe .
```

### Configure

```bash
cp cfg.yml.template cfg.yml
# Edit cfg.yml with your upstream API credentials
```

### Run

```bash
./api_adapter_go [port]
# Default port: 16001
```

Or with `go run`:

```bash
go run . [port]
```

### Environment Variable

Set `ADAPTER_CONFIG` to point to an alternative config file path:

```bash
ADAPTER_CONFIG=/path/to/cfg.yml ./api_adapter_go
```

## Usage with Claude Code

Set these environment variables:

```sh
export ANTHROPIC_BASE_URL=http://127.0.0.1:16001
export ANTHROPIC_AUTH_TOKEN=<llm_api_key from cfg.yml>
export ANTHROPIC_MODEL=deepseek-chat
export ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/messages` | Create a message (streaming supported) |
| GET | `/v1/models` | List available models |
| GET | `/v1/models/{model_id}` | Get model details |
| POST | `/v1/messages/count_tokens` | Estimate token count |
| GET | `/health` | Health check |
| GET | `/` | Welcome / service info |

## Authentication

Pass the API key via:
- `x-api-key` header
- `Authorization: Bearer <key>` header

## Configuration

```yaml
api:
  llm_api_uri: https://api.deepseek.com/v1   # Upstream base URL
  llm_api_key: sk-xxx                          # Upstream API key
  llm_model_name: deepseek-chat                # Default model
```

## Architecture

```
main.go              — Entry point, server setup, graceful shutdown
config/config.go     — YAML configuration loading
handler/
  middleware.go      — Auth, CORS, JSON response helpers
  messages.go        — POST /v1/messages (stream + non-stream)
  models.go          — GET /v1/models, GET /v1/models/{id}, POST /v1/messages/count_tokens, /health, /
converter/
  anthropic_to_openai.go  — Anthropic → OpenAI request conversion (messages, tools, tool_choice)
  openai_to_anthropic.go  — OpenAI → Anthropic response conversion
  sse.go                  — OpenAI SSE → Anthropic SSE stream conversion
```
