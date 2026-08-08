package converter

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"sync"
	"time"
)

// GenerateAnthropicSSE reads an OpenAI SSE stream from reader and writes
// Anthropic-format SSE events to writer.
func GenerateAnthropicSSE(reader io.Reader, writer io.Writer, anthropicModel string) error {
	msgID := GenerateMsgID()
	thinkingBlockIndex := -1
	textBlockIndex := -1
	toolBlockIndices := make(map[int]int) // OpenAI tool_call index -> Anthropic content index
	nextBlockIndex := 0
	closedBlocks := make(map[int]bool)
	outputTokens := 0
	finishReason := ""
	lastPing := time.Now()
	pingInterval := 30 * time.Second

	var mu sync.Mutex // protects the state above

	// emit* helpers that write SSE frames to the writer.
	// They acquire the mutex internally for thread-safety.
	emit := func(frame []byte) error {
		mu.Lock()
		defer mu.Unlock()
		_, err := writer.Write(frame)
		return err
	}

	emitBlockStart := func(index int, block map[string]interface{}) error {
		return emit(eventFrame("content_block_start", map[string]interface{}{
			"type":          "content_block_start",
			"index":         index,
			"content_block": block,
		}))
	}

	emitBlockDelta := func(index int, delta map[string]interface{}) error {
		return emit(eventFrame("content_block_delta", map[string]interface{}{
			"type":  "content_block_delta",
			"index": index,
			"delta": delta,
		}))
	}

	emitBlockStop := func(index int) error {
		return emit(eventFrame("content_block_stop", map[string]interface{}{
			"type":  "content_block_stop",
			"index": index,
		}))
	}

	// message_start
	startEvent := map[string]interface{}{
		"type": "message_start",
		"message": map[string]interface{}{
			"id":           msgID,
			"type":         "message",
			"role":         "assistant",
			"content":      []interface{}{},
			"model":        anthropicModel,
			"stop_reason":  nil,
			"stop_sequence": nil,
			"usage": map[string]interface{}{
				"input_tokens":  0,
				"output_tokens": 0,
			},
		},
	}
	if err := emit(eventFrame("message_start", startEvent)); err != nil {
		return fmt.Errorf("write message_start: %w", err)
	}

	scanner := bufio.NewScanner(reader)
	// Increase buffer size for large lines (OpenAI streaming can produce large chunks)
	scanner.Buffer(make([]byte, 0, 64*1024), 2*1024*1024)

	lineCount := 0
	for scanner.Scan() {
		lineCount++
		line := scanner.Text()
		if line == "" {
			continue
		}

		if !strings.HasPrefix(line, "data: ") {
			continue
		}

		dataStr := strings.TrimPrefix(line, "data: ")
		dataStr = strings.TrimSpace(dataStr)
		if dataStr == "[DONE]" {
			break
		}

		var chunk map[string]interface{}
		if err := json.Unmarshal([]byte(dataStr), &chunk); err != nil {
			continue
		}

		mu.Lock()

		// Extract usage (prompt_tokens tracked but only completion_tokens sent in SSE message_delta)
		if chunkUsage, ok := chunk["usage"].(map[string]interface{}); ok {
			if ct, ok := chunkUsage["completion_tokens"].(float64); ok {
				outputTokens = int(ct)
			}
		}

		choices, _ := chunk["choices"].([]interface{})
		if len(choices) == 0 {
			mu.Unlock()
			continue
		}

		choice, _ := choices[0].(map[string]interface{})
		if choice == nil {
			mu.Unlock()
			continue
		}

		if cf, ok := choice["finish_reason"].(string); ok && cf != "" {
			finishReason = cf
		}

		delta, _ := choice["delta"].(map[string]interface{})
		if delta == nil {
			mu.Unlock()
			continue
		}

		// Reasoning/thinking content (e.g. DeepSeek-R1)
		reasoningText, _ := delta["reasoning_content"].(string)
		if reasoningText != "" {
			if thinkingBlockIndex < 0 {
				thinkingBlockIndex = nextBlockIndex
				nextBlockIndex++
				if err := emitBlockStart(thinkingBlockIndex, map[string]interface{}{
					"type":      "thinking",
					"thinking":  "",
					"signature": "",
				}); err != nil {
					mu.Unlock()
					return fmt.Errorf("write thinking block start: %w", err)
				}
			}
			if err := emitBlockDelta(thinkingBlockIndex, map[string]interface{}{
				"type":     "thinking_delta",
				"thinking": reasoningText,
			}); err != nil {
				mu.Unlock()
				return fmt.Errorf("write thinking delta: %w", err)
			}
		}

		// Text content
		contentText, _ := delta["content"].(string)
		if contentText != "" {
			// Close thinking block before starting text
			if thinkingBlockIndex >= 0 && !closedBlocks[thinkingBlockIndex] {
				if err := emitBlockStop(thinkingBlockIndex); err != nil {
					mu.Unlock()
					return fmt.Errorf("write thinking block stop: %w", err)
				}
				closedBlocks[thinkingBlockIndex] = true
			}

			if textBlockIndex < 0 {
				textBlockIndex = nextBlockIndex
				nextBlockIndex++
				if err := emitBlockStart(textBlockIndex, map[string]interface{}{
					"type": "text",
					"text": "",
				}); err != nil {
					mu.Unlock()
					return fmt.Errorf("write text block start: %w", err)
				}
			}

			if err := emitBlockDelta(textBlockIndex, map[string]interface{}{
				"type": "text_delta",
				"text": contentText,
			}); err != nil {
				mu.Unlock()
				return fmt.Errorf("write text delta: %w", err)
			}
		}

		// Tool calls
		toolCalls, _ := delta["tool_calls"].([]interface{})
		for _, tc := range toolCalls {
			tcMap, ok := tc.(map[string]interface{})
			if !ok {
				continue
			}

			tcIdx := 0
			if idx, ok := tcMap["index"].(float64); ok {
				tcIdx = int(idx)
			}

			if _, exists := toolBlockIndices[tcIdx]; !exists {
				toolBlockIndices[tcIdx] = nextBlockIndex
				nextBlockIndex++

				tcID, _ := tcMap["id"].(string)
				funcMap, _ := tcMap["function"].(map[string]interface{})
				tcName := ""
				if funcMap != nil {
					tcName, _ = funcMap["name"].(string)
				}

				if err := emitBlockStart(toolBlockIndices[tcIdx], map[string]interface{}{
					"type":  "tool_use",
					"id":    tcID,
					"name":  tcName,
					"input": map[string]interface{}{},
				}); err != nil {
					mu.Unlock()
					return fmt.Errorf("write tool block start: %w", err)
				}
			}

			funcMap, _ := tcMap["function"].(map[string]interface{})
			if funcMap != nil {
				args, _ := funcMap["arguments"].(string)
				if args != "" {
					if err := emitBlockDelta(toolBlockIndices[tcIdx], map[string]interface{}{
						"type":         "input_json_delta",
						"partial_json": args,
					}); err != nil {
						mu.Unlock()
						return fmt.Errorf("write tool delta: %w", err)
					}
				}
			}
		}

		// Periodic ping to prevent proxy/gateway timeout
		now := time.Now()
		if now.Sub(lastPing) >= pingInterval {
			if _, err := writer.Write([]byte("event: ping\ndata: {}\n\n")); err != nil {
				mu.Unlock()
				return fmt.Errorf("write ping: %w", err)
			}
			lastPing = now
		}

		mu.Unlock()
	}

	if err := scanner.Err(); err != nil {
		return fmt.Errorf("scan upstream stream: %w", err)
	}

	mu.Lock()
	defer mu.Unlock()

	// Close any unclosed content blocks
	for i := 0; i < nextBlockIndex; i++ {
		if !closedBlocks[i] {
			if err := emitBlockStop(i); err != nil {
				return fmt.Errorf("write final block stop %d: %w", i, err)
			}
		}
	}

	anthropicStop := "end_turn"
	if mapped, ok := FinishReasonMap[finishReason]; ok {
		anthropicStop = mapped
	}

	// message_delta
	msgDelta := map[string]interface{}{
		"type": "message_delta",
		"delta": map[string]interface{}{
			"stop_reason":  anthropicStop,
			"stop_sequence": nil,
		},
		"usage": map[string]interface{}{
			"output_tokens": outputTokens,
		},
	}
	if err := emit(eventFrame("message_delta", msgDelta)); err != nil {
		return fmt.Errorf("write message_delta: %w", err)
	}

	// message_stop
	msgStop := map[string]interface{}{"type": "message_stop"}
	if err := emit(eventFrame("message_stop", msgStop)); err != nil {
		return fmt.Errorf("write message_stop: %w", err)
	}

	return nil
}

// eventFrame formats an SSE event frame with the given event type and JSON data.
func eventFrame(event string, data interface{}) []byte {
	jsonData, _ := json.Marshal(data)
	return []byte(fmt.Sprintf("event: %s\ndata: %s\n\n", event, string(jsonData)))
}
