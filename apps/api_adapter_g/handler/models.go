package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"api_adapter_go/converter"
)

// ModelsHandler handles Anthropic-format model listing endpoints.
type ModelsHandler struct {
	ModelName string
}

// ListModels handles GET /v1/models — returns available models in Anthropic format.
func (h *ModelsHandler) ListModels(w http.ResponseWriter, r *http.Request) {
	data := map[string]interface{}{
		"data": []map[string]interface{}{
			{
				"id":           h.ModelName,
				"type":         "model",
				"display_name": h.ModelName,
				"created_at":   "2024-01-01T00:00:00Z",
			},
		},
		"has_more": false,
		"first_id": h.ModelName,
		"last_id":  h.ModelName,
	}
	WriteJSON(w, http.StatusOK, data)
}

// GetModel handles GET /v1/models/{model_id} — returns a single model.
func (h *ModelsHandler) GetModel(w http.ResponseWriter, r *http.Request) {
	// Extract model_id from URL path: /v1/models/{model_id}
	modelID := strings.TrimPrefix(r.URL.Path, "/v1/models/")
	if modelID == "" {
		WriteError(w, http.StatusBadRequest, "invalid_request_error", "model_id is required")
		return
	}

	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"id":           modelID,
		"type":         "model",
		"display_name": modelID,
		"created_at":   "2024-01-01T00:00:00Z",
	})
}

// CountTokens handles POST /v1/messages/count_tokens — rough token count estimation.
func (h *ModelsHandler) CountTokens(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		WriteError(w, http.StatusMethodNotAllowed, "invalid_request_error", "method not allowed")
		return
	}

	var data map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&data); err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_request_error", "Request body is required")
		return
	}

	messages, _ := data["messages"]
	system, _ := data["system"]
	tools, _ := data["tools"]

	systemText := extractSystemText(system)
	messagesJSON, _ := json.Marshal(messages)
	toolsJSON, _ := json.Marshal(tools)

	totalChars := len(systemText) + len(messagesJSON) + len(toolsJSON)
	inputTokens := totalChars / 3
	if inputTokens < 1 {
		inputTokens = 1
	}

	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"input_tokens": inputTokens,
	})
}

func extractSystemText(system interface{}) string {
	switch s := system.(type) {
	case string:
		return s
	case []interface{}:
		var parts []string
		for _, block := range s {
			if b, ok := block.(map[string]interface{}); ok {
				if b["type"] == "text" {
					if text, ok := b["text"].(string); ok {
						parts = append(parts, text)
					}
				}
			}
		}
		return strings.Join(parts, "")
	default:
		return ""
	}
}

// Health handles GET /health — health check endpoint.
func Health(w http.ResponseWriter, r *http.Request, modelName, upstreamURI string) {
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"status":         "healthy",
		"adapter":        "openai-to-anthropic",
		"upstream_model": modelName,
		"upstream_uri":   upstreamURI,
		"timestamp":      converter.NowUnix(),
	})
}

// Welcome handles GET / — welcome/info endpoint.
func Welcome(w http.ResponseWriter, r *http.Request, modelName, upstreamURI string) {
	WriteJSON(w, http.StatusOK, map[string]interface{}{
		"status":               200,
		"msg":                  "LLM API Adapter - OpenAI to Anthropic API converter",
		"upstream_model":       modelName,
		"upstream_uri":         upstreamURI,
		"anthropic_api_version": converter.AnthropicVersion,
		"endpoints": map[string]interface{}{
			"messages": "/v1/messages",
			"models":   "/v1/models",
			"health":   "/health",
		},
		"timestamp": converter.NowUnix(),
	})
}

// logRequest logs incoming requests.
func logRequest(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log.Printf("[INFO] %s %s", r.Method, r.URL.Path)
		next.ServeHTTP(w, r)
	})
}
