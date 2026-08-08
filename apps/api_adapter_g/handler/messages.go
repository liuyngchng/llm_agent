package handler

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"api_adapter_go/converter"
)

// MessagesHandler holds dependencies for the /v1/messages endpoint.
type MessagesHandler struct {
	LLMAPIURI string
	LLMAPIKey string
	ModelName string
	Client    *http.Client
}

// NewMessagesHandler creates a MessagesHandler with a default HTTP client.
func NewMessagesHandler(uri, key, model string) *MessagesHandler {
	return &MessagesHandler{
		LLMAPIURI: uri,
		LLMAPIKey: key,
		ModelName: model,
		Client: &http.Client{
			Timeout: 300 * time.Second,
		},
	}
}

// ServeHTTP handles POST /v1/messages — the main message creation endpoint.
func (h *MessagesHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()

	if r.Method != http.MethodPost {
		WriteError(w, http.StatusMethodNotAllowed, "invalid_request_error", "method not allowed")
		return
	}

	// Read body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_request_error", "failed to read request body")
		return
	}
	defer r.Body.Close()

	var data map[string]interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		WriteError(w, http.StatusBadRequest, "invalid_request_error", "invalid JSON in request body")
		return
	}

	log.Printf("[DEBUG] Request body: %s", truncateStr(string(body), 500))

	// Validate messages
	messages, ok := data["messages"].([]interface{})
	if !ok || len(messages) == 0 {
		WriteError(w, http.StatusBadRequest, "invalid_request_error", "messages must be a non-empty list")
		return
	}

	stream, _ := data["stream"].(bool)
	anthropicModel := converter.AnthropicModel(data, h.ModelName)

	// Convert request
	openaiReq, err := converter.AnthropicToOpenAIRequest(data, h.ModelName)
	if err != nil {
		log.Printf("[ERROR] Failed to convert request: %v", err)
		WriteError(w, http.StatusInternalServerError, "internal_error", "failed to convert request")
		return
	}

	upstreamURL := fmt.Sprintf("%s/chat/completions", h.LLMAPIURI)
	log.Printf("[INFO] forward to %s, model=%s, stream=%v", upstreamURL, h.ModelName, stream)

	reqBody, _ := json.Marshal(openaiReq)

	if stream {
		h.handleStream(w, r, upstreamURL, reqBody, anthropicModel, startTime)
	} else {
		h.handleNonStream(w, r, upstreamURL, reqBody, anthropicModel, startTime)
	}
}

func (h *MessagesHandler) handleStream(w http.ResponseWriter, r *http.Request, upstreamURL string, reqBody []byte, anthropicModel string, startTime time.Time) {
	// bytes.NewReader implements io.Reader and is recognized by net/http which
	// auto-sets Content-Length; avoids chunked transfer encoding.
	upstreamReq, err := http.NewRequestWithContext(r.Context(), http.MethodPost, upstreamURL, bytes.NewReader(reqBody))
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", "failed to create upstream request")
		return
	}
	upstreamReq.Header.Set("Content-Type", "application/json")
	upstreamReq.Header.Set("Authorization", "Bearer "+h.LLMAPIKey)

	resp, err := h.Client.Do(upstreamReq)
	if err != nil {
		log.Printf("[ERROR] Upstream request failed: %v", err)
		WriteError(w, http.StatusBadGateway, "api_error", fmt.Sprintf("Upstream API error: %v", err))
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		log.Printf("[ERROR] Upstream error: %d - %s", resp.StatusCode, string(body))
		WriteError(w, http.StatusBadGateway, "api_error", fmt.Sprintf("Upstream API returned %d", resp.StatusCode))
		return
	}

	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Request-Id", converter.GenerateMsgID())
	w.WriteHeader(http.StatusOK)

	if err := converter.GenerateAnthropicSSE(resp.Body, w, anthropicModel); err != nil {
		log.Printf("[ERROR] SSE conversion error: %v", err)
	}

	elapsed := time.Since(startTime)
	log.Printf("[INFO] Stream request processed in %.2fs", elapsed.Seconds())
}

func (h *MessagesHandler) handleNonStream(w http.ResponseWriter, r *http.Request, upstreamURL string, reqBody []byte, anthropicModel string, startTime time.Time) {
	// bytes.NewReader implements io.Reader and is recognized by net/http which
	// auto-sets Content-Length; avoids chunked transfer encoding.
	upstreamReq, err := http.NewRequestWithContext(r.Context(), http.MethodPost, upstreamURL, bytes.NewReader(reqBody))
	if err != nil {
		WriteError(w, http.StatusInternalServerError, "internal_error", "failed to create upstream request")
		return
	}
	upstreamReq.Header.Set("Content-Type", "application/json")
	upstreamReq.Header.Set("Authorization", "Bearer "+h.LLMAPIKey)

	resp, err := h.Client.Do(upstreamReq)
	if err != nil {
		log.Printf("[ERROR] Upstream request failed: %v", err)
		WriteError(w, http.StatusBadGateway, "api_error", fmt.Sprintf("Upstream API error: %v", err))
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		log.Printf("[ERROR] Upstream error: %d - %s", resp.StatusCode, string(body))
		WriteError(w, http.StatusBadGateway, "api_error", fmt.Sprintf("Upstream API returned %d", resp.StatusCode))
		return
	}

	var openaiResp map[string]interface{}
	if err := json.Unmarshal(body, &openaiResp); err != nil {
		log.Printf("[ERROR] Failed to parse upstream response: %v", err)
		WriteError(w, http.StatusInternalServerError, "internal_error", "failed to parse upstream response")
		return
	}

	anthropicResp := converter.OpenAIToAnthropicResponse(openaiResp, anthropicModel)
	msgID, _ := anthropicResp["id"].(string)
	w.Header().Set("X-Request-Id", msgID)
	WriteJSON(w, http.StatusOK, anthropicResp)

	elapsed := time.Since(startTime)
	log.Printf("[INFO] Non-stream request processed in %.2fs", elapsed.Seconds())
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func truncateStr(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}
