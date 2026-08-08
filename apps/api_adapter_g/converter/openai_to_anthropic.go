package converter

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"
)

// ---------------------------------------------------------------------------
// OpenAI → Anthropic: response conversion (non-streaming)
// ---------------------------------------------------------------------------

// OpenAIToAnthropicResponse converts an OpenAI Chat Completions response
// to the Anthropic Messages API response format.
func OpenAIToAnthropicResponse(openaiResp map[string]interface{}, anthropicModel string) map[string]interface{} {
	msgID := GenerateMsgID()

	choices, _ := openaiResp["choices"].([]interface{})
	var choice map[string]interface{}
	if len(choices) > 0 {
		choice, _ = choices[0].(map[string]interface{})
	}
	if choice == nil {
		choice = map[string]interface{}{}
	}

	message, _ := choice["message"].(map[string]interface{})
	if message == nil {
		message = map[string]interface{}{}
	}

	contentText, _ := message["content"].(string)
	reasoningText, _ := message["reasoning_content"].(string)
	finishReason, _ := choice["finish_reason"].(string)
	if finishReason == "" {
		finishReason = "stop"
	}
	stopReason := FinishReasonMap[finishReason]
	if stopReason == "" {
		stopReason = "end_turn"
	}

	usage, _ := openaiResp["usage"].(map[string]interface{})
	inputTokens := 0
	outputTokens := 0
	if usage != nil {
		if it, ok := usage["prompt_tokens"].(float64); ok {
			inputTokens = int(it)
		}
		if ot, ok := usage["completion_tokens"].(float64); ok {
			outputTokens = int(ot)
		}
	}

	// Build content blocks
	contentBlocks := make([]map[string]interface{}, 0)

	if reasoningText != "" {
		contentBlocks = append(contentBlocks, map[string]interface{}{
			"type":      "thinking",
			"thinking":  reasoningText,
			"signature": "",
		})
	}

	if contentText != "" {
		contentBlocks = append(contentBlocks, map[string]interface{}{
			"type": "text",
			"text": contentText,
		})
	}

	toolCalls, _ := message["tool_calls"].([]interface{})
	for _, tc := range toolCalls {
		tcMap, ok := tc.(map[string]interface{})
		if !ok {
			continue
		}
		funcMap, _ := tcMap["function"].(map[string]interface{})
		if funcMap == nil {
			continue
		}
		argsStr, _ := funcMap["arguments"].(string)

		var toolInput interface{}
		if err := json.Unmarshal([]byte(argsStr), &toolInput); err != nil {
			toolInput = map[string]interface{}{
				"arguments": argsStr,
			}
		}

		contentBlocks = append(contentBlocks, map[string]interface{}{
			"type":  "tool_use",
			"id":    tcMap["id"],
			"name":  funcMap["name"],
			"input": toolInput,
		})
	}

	return map[string]interface{}{
		"id":           msgID,
		"type":         "message",
		"role":         "assistant",
		"model":        anthropicModel,
		"content":      contentBlocks,
		"stop_reason":  stopReason,
		"stop_sequence": nil,
		"usage": map[string]interface{}{
			"input_tokens":  inputTokens,
			"output_tokens": outputTokens,
		},
	}
}

// GenerateMsgID creates a unique message ID for Anthropic responses.
func GenerateMsgID() string {
	b := make([]byte, 6)
	if _, err := rand.Read(b); err != nil {
		// Fallback: should never happen
		return fmt.Sprintf("msg_%s", hex.EncodeToString([]byte(fmt.Sprintf("%d", time.Now().UnixNano()))))
	}
	return fmt.Sprintf("msg_%s", hex.EncodeToString(b))
}
