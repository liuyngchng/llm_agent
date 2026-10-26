# api_adapter_go

OpenAI-to-Anthropic API protocol adapter written in Go. Accepts Anthropic Messages API requests and forwards them to an OpenAI-compatible upstream LLM API.

## Quick Start

### 1. Configure

```bash
cp cfg.yml.template cfg.yml
# Edit cfg.yml with your upstream API credentials
```

### 2. Run (bare metal or Docker)

**Bare metal — go run:**

```bash
go run . [port]
# Default port: 16001
```

**Bare metal — binary:**

```bash
# Linux (amd64)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o api_adapter_linux_amd64 .
./api_adapter_linux_amd64

# Windows (amd64)
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o api_adapter_windows_amd64.exe .
api_adapter_windows_amd64.exe
```

**Docker — build + deploy:**

```bash
# Build binaries + Docker image (image: llm_api_adapter_g:1.1)
./deploy/build.sh

# Deploy container only (no rebuild, uses existing image)
./deploy/deploy.sh

# One-shot build + deploy
./deploy/build.sh run
```

### 3. Test

```bash
./deploy/test.sh              # default 127.0.0.1:16001
./deploy/test.sh 8080         # custom port
./deploy/test.sh 192.168.1.1  # remote host
```

## Docker Volume Mounts

When running via `./deploy/deploy.sh` or `./deploy/build.sh run`, the following host directories are mounted:

| Host directory | Container directory | Purpose |
|---|---|---|
| `apps/api_adapter_g/cfg/` | `/opt/app/cfg/` | Configuration (`cfg.yml`) |
| `apps/api_adapter_g/logs/` | `/opt/app/logs/` | Application logs |

On first deploy, create `cfg/cfg.yml` manually from `cfg.yml.template` and fill in real credentials before running deploy. The deploy script will refuse to start if this file is missing.

## Environment Variable

Set `ADAPTER_CONFIG` to point to an alternative config file path:

```bash
ADAPTER_CONFIG=/path/to/cfg.yml ./api_adapter_go
```

The Docker container already sets `ADAPTER_CONFIG=/opt/app/cfg/cfg.yml` — just edit `cfg/cfg.yml` on the host.

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

## Scripts

| Script | Purpose |
|---|---|
| `deploy/build.sh [all\|bin\|run]` | Build Go binaries + Docker image; `run` also deploys |
| `deploy/build.bat` | Windows build (binaries only) |
| `deploy/deploy.sh` | Deploy Docker container from existing image (no build) |
| `deploy/test.sh [host:port]` | Smoke-test all API endpoints |

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
