// Package converter handles all Anthropic ↔ OpenAI protocol conversions.
package converter

import (
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// FinishReasonMap maps OpenAI finish_reason values to Anthropic stop_reason values.
var FinishReasonMap = map[string]string{
	"stop":           "end_turn",
	"length":         "max_tokens",
	"tool_calls":     "tool_use",
	"content_filter": "end_turn",
}

const AnthropicVersion = "2023-06-01"

// ---------------------------------------------------------------------------
// Anthropic → OpenAI: request conversion
// ---------------------------------------------------------------------------

// AnthropicToOpenAIRequest converts an Anthropic Messages API request body
// into an OpenAI Chat Completions request body.
func AnthropicToOpenAIRequest(anthropicData map[string]interface{}, modelName string) (map[string]interface{}, error) {
	systemPrompt, _ := anthropicData["system"]
	anthropicMessages, _ := anthropicData["messages"].([]interface{})
	maxTokens, _ := anthropicData["max_tokens"].(float64)
	if maxTokens == 0 {
		maxTokens = 4096
	}
	// Default to 0.7 when not provided, matching Python adapter behavior.
	temperature := 0.7
	if val, ok := anthropicData["temperature"]; ok {
		if t, ok := val.(float64); ok {
			temperature = t
		}
	}
	stream, _ := anthropicData["stream"].(bool)
	stopSequences, _ := anthropicData["stop_sequences"]
	topP, _ := anthropicData["top_p"]
	anthropicTools, _ := anthropicData["tools"]
	anthropicToolChoice, _ := anthropicData["tool_choice"]
	userID := ""
	if meta, ok := anthropicData["metadata"].(map[string]interface{}); ok {
		if uid, ok := meta["user_id"].(string); ok {
			userID = uid
		}
	}

	openaiMessages := AnthropicMessagesToOpenAI(anthropicMessages, systemPrompt)

	openaiReq := map[string]interface{}{
		"model":       modelName,
		"messages":    openaiMessages,
		"max_tokens":  maxTokens,
		"temperature": temperature,
		"stream":      stream,
	}

	if stopSequences != nil {
		openaiReq["stop"] = stopSequences
	}
	if topP != nil {
		openaiReq["top_p"] = topP
	}

	if tools := AnthropicToolsToOpenAI(anthropicTools); tools != nil {
		openaiReq["tools"] = tools
	}

	if userID != "" {
		openaiReq["user"] = userID
	}

	if tc := AnthropicToolChoiceToOpenAI(anthropicToolChoice); tc != nil {
		openaiReq["tool_choice"] = tc
	}

	return openaiReq, nil
}

// ---------------------------------------------------------------------------
// Anthropic → OpenAI: tools
// ---------------------------------------------------------------------------

// AnthropicToolsToOpenAI converts Anthropic-format tools to OpenAI-format tools.
func AnthropicToolsToOpenAI(anthropicTools interface{}) interface{} {
	tools, ok := anthropicTools.([]interface{})
	if !ok || len(tools) == 0 {
		return nil
	}

	openaiTools := make([]map[string]interface{}, 0, len(tools))
	for _, t := range tools {
		tool, ok := t.(map[string]interface{})
		if !ok {
			continue
		}
		inputSchema, _ := tool["input_schema"]
		if inputSchema == nil {
			inputSchema = map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			}
		}
		openaiTools = append(openaiTools, map[string]interface{}{
			"type": "function",
			"function": map[string]interface{}{
				"name":        tool["name"],
				"description": tool["description"],
				"parameters":  inputSchema,
			},
		})
	}
	return openaiTools
}

// AnthropicToolChoiceToOpenAI converts Anthropic tool_choice to OpenAI format.
func AnthropicToolChoiceToOpenAI(toolChoice interface{}) interface{} {
	tc, ok := toolChoice.(map[string]interface{})
	if !ok {
		return nil
	}
	tcType, _ := tc["type"].(string)
	switch tcType {
	case "auto":
		return "auto"
	case "any":
		return "required"
	case "tool":
		if name, ok := tc["name"].(string); ok && name != "" {
			return map[string]interface{}{
				"type": "function",
				"function": map[string]interface{}{
					"name": name,
				},
			}
		}
	}
	return "auto"
}

// ---------------------------------------------------------------------------
// Anthropic → OpenAI: messages
// ---------------------------------------------------------------------------

// AnthropicMessagesToOpenAI converts Anthropic-format messages to OpenAI-format messages.
func AnthropicMessagesToOpenAI(anthropicMessages []interface{}, systemPrompt interface{}) []map[string]interface{} {
	openaiMessages := make([]map[string]interface{}, 0)

	// Handle system prompt
	if sp, ok := systemPrompt.(string); ok && sp != "" {
		openaiMessages = append(openaiMessages, map[string]interface{}{
			"role":    "system",
			"content": sp,
		})
	} else if spList, ok := systemPrompt.([]interface{}); ok {
		systemText := extractTextFromBlocks(spList)
		if systemText != "" {
			openaiMessages = append(openaiMessages, map[string]interface{}{
				"role":    "system",
				"content": systemText,
			})
		}
	}

	for _, m := range anthropicMessages {
		msg, ok := m.(map[string]interface{})
		if !ok {
			continue
		}
		role, _ := msg["role"].(string)
		content := msg["content"]

		switch role {
		case "user":
			msgs := convertAnthropicUserContent(content)
			openaiMessages = append(openaiMessages, msgs...)
		case "assistant":
			oaContent, oaToolCalls := convertAnthropicAssistantContent(content)
			oaMsg := map[string]interface{}{
				"role":    "assistant",
				"content": oaContent,
			}
			if oaToolCalls != nil {
				oaMsg["tool_calls"] = oaToolCalls
			}
			openaiMessages = append(openaiMessages, oaMsg)
		}
	}

	return fixToolMessageOrdering(openaiMessages)
}

// ---------------------------------------------------------------------------
// Anthropic → OpenAI: content helpers
// ---------------------------------------------------------------------------

func convertAnthropicUserContent(content interface{}) []map[string]interface{} {
	switch c := content.(type) {
	case string:
		return []map[string]interface{}{{"role": "user", "content": c}}
	case []interface{}:
		return convertAnthropicUserContentBlocks(c)
	default:
		return []map[string]interface{}{{"role": "user", "content": fmt.Sprintf("%v", c)}}
	}
}

func convertAnthropicUserContentBlocks(blocks []interface{}) []map[string]interface{} {
	var textParts []string
	var imageParts []map[string]interface{}
	var toolMessages []map[string]interface{}

	for _, b := range blocks {
		block, ok := b.(map[string]interface{})
		if !ok {
			continue
		}
		blockType, _ := block["type"].(string)
		switch blockType {
		case "text":
			if text, ok := block["text"].(string); ok {
				textParts = append(textParts, text)
			}
		case "image":
			source, _ := block["source"].(map[string]interface{})
			if source != nil {
				mediaType, _ := source["media_type"].(string)
				if mediaType == "" {
					mediaType = "image/png"
				}
				data, _ := source["data"].(string)
				imageParts = append(imageParts, map[string]interface{}{
					"type": "image_url",
					"image_url": map[string]interface{}{
						"url": fmt.Sprintf("data:%s;base64,%s", mediaType, data),
					},
				})
			}
		case "tool_result":
			toolUseID, _ := block["tool_use_id"].(string)
			toolContent := block["content"]
			toolText := extractTextFromBlocksOrString(toolContent)
			toolMessages = append(toolMessages, map[string]interface{}{
				"role":         "tool",
				"tool_call_id": toolUseID,
				"content":      toolText,
			})
		}
	}

	messages := make([]map[string]interface{}, 0)

	if len(textParts) > 0 || len(imageParts) > 0 {
		if len(imageParts) > 0 && len(textParts) == 0 {
			messages = append(messages, map[string]interface{}{
				"role":    "user",
				"content": imageParts,
			})
		} else if len(imageParts) > 0 && len(textParts) > 0 {
			result := []map[string]interface{}{
				{"type": "text", "text": strings.Join(textParts, "\n")},
			}
			for _, img := range imageParts {
				result = append(result, img)
			}
			messages = append(messages, map[string]interface{}{
				"role":    "user",
				"content": result,
			})
		} else {
			messages = append(messages, map[string]interface{}{
				"role":    "user",
				"content": strings.Join(textParts, "\n"),
			})
		}
	}

	messages = append(messages, toolMessages...)
	return messages
}

func convertAnthropicAssistantContent(content interface{}) (string, interface{}) {
	switch c := content.(type) {
	case string:
		return c, nil
	case []interface{}:
		return convertAnthropicAssistantContentBlocks(c)
	default:
		return fmt.Sprintf("%v", c), nil
	}
}

func convertAnthropicAssistantContentBlocks(blocks []interface{}) (string, interface{}) {
	var textParts []string
	var toolCalls []map[string]interface{}

	for _, b := range blocks {
		block, ok := b.(map[string]interface{})
		if !ok {
			continue
		}
		blockType, _ := block["type"].(string)
		switch blockType {
		case "text":
			if text, ok := block["text"].(string); ok {
				textParts = append(textParts, text)
			}
		case "tool_use":
			args, _ := json.Marshal(block["input"])
			toolCalls = append(toolCalls, map[string]interface{}{
				"id":   block["id"],
				"type": "function",
				"function": map[string]interface{}{
					"name":      block["name"],
					"arguments": string(args),
				},
			})
		}
	}

	contentText := strings.Join(textParts, "\n")
	if len(toolCalls) > 0 {
		return contentText, toolCalls
	}
	return contentText, nil
}

// ---------------------------------------------------------------------------
// Anthropic → OpenAI: tool message ordering fix
// ---------------------------------------------------------------------------

// fixToolMessageOrdering ensures tool messages immediately follow their
// corresponding assistant(tool_calls) message, with any user messages moved
// after the tool messages. This satisfies OpenAI's ordering requirement.
func fixToolMessageOrdering(messages []map[string]interface{}) []map[string]interface{} {
	if len(messages) == 0 {
		return messages
	}

	result := make([]map[string]interface{}, 0, len(messages))
	i := 0
	for i < len(messages) {
		msg := messages[i]

		toolCalls, hasToolCalls := msg["tool_calls"].([]interface{})
		if msg["role"] != "assistant" || !hasToolCalls || len(toolCalls) == 0 {
			result = append(result, msg)
			i++
			continue
		}

		// Collect tool call IDs from this assistant message
		tcIDs := make(map[string]bool)
		for _, tc := range toolCalls {
			if tcMap, ok := tc.(map[string]interface{}); ok {
				if id, ok := tcMap["id"].(string); ok {
					tcIDs[id] = true
				}
			}
		}

		result = append(result, msg)

		// Scan forward for tool messages and interleaved user messages
		var toolMsgs []map[string]interface{}
		var userMsgs []map[string]interface{}
		j := i + 1
		for j < len(messages) {
			nxt := messages[j]
			if nxt["role"] == "tool" {
				if tid, ok := nxt["tool_call_id"].(string); ok && tcIDs[tid] {
					toolMsgs = append(toolMsgs, nxt)
					j++
					continue
				}
			}
			if nxt["role"] == "user" {
				userMsgs = append(userMsgs, nxt)
				j++
				continue
			}
			break
		}

		// Tool messages first, then user messages
		result = append(result, toolMsgs...)
		result = append(result, userMsgs...)
		i = j
	}
	return result
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func extractTextFromBlocks(blocks []interface{}) string {
	var parts []string
	for _, b := range blocks {
		if block, ok := b.(map[string]interface{}); ok {
			if block["type"] == "text" {
				if text, ok := block["text"].(string); ok {
					parts = append(parts, text)
				}
			}
		}
	}
	return strings.Join(parts, "")
}

func extractTextFromBlocksOrString(content interface{}) string {
	switch c := content.(type) {
	case string:
		return c
	case []interface{}:
		return extractTextFromBlocks(c)
	default:
		return fmt.Sprintf("%v", c)
	}
}

// NowUnix returns the current Unix timestamp.
func NowUnix() int64 {
	return time.Now().Unix()
}

// AnthropicModel extracts the model name from the request, falling back to the
// configured default.
func AnthropicModel(data map[string]interface{}, defaultModel string) string {
	if model, ok := data["model"].(string); ok && model != "" {
		return model
	}
	return defaultModel
}
