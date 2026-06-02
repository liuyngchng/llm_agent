package llm_api_adapter.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/**
 * Reads OpenAI SSE stream and emits Anthropic SSE events via a callback.
 */
@Service
public class SseConversionService {
    private static final Logger log = LoggerFactory.getLogger(SseConversionService.class);

    private final ObjectMapper mapper = new ObjectMapper();
    private static final Map<String, String> FINISH_REASON_MAP = new HashMap<>();
    static {
        FINISH_REASON_MAP.put("stop", "end_turn");
        FINISH_REASON_MAP.put("length", "max_tokens");
        FINISH_REASON_MAP.put("tool_calls", "tool_use");
        FINISH_REASON_MAP.put("content_filter", "end_turn");
    }

    @SuppressWarnings("unchecked")
    public void convertStream(InputStream upstreamStream, String anthropicModel,
                               SseCallback callback) throws IOException {

        String msgId = "msg_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        int thinkingBlockIndex = -1;
        int textBlockIndex = -1;
        int nextBlockIndex = 0;
        Set<Integer> closedBlocks = new HashSet<>();
        Map<Integer, Integer> tcIndexMap = new HashMap<>();
        int inputTokens = 0, outputTokens = 0;
        String finishReason = null;

        // message_start
        Map<String, Object> startMsg = new LinkedHashMap<>();
        startMsg.put("id", msgId);
        startMsg.put("type", "message");
        startMsg.put("role", "assistant");
        startMsg.put("content", new ArrayList<>());
        startMsg.put("model", anthropicModel);
        startMsg.put("stop_reason", null);
        startMsg.put("stop_sequence", null);
        startMsg.put("usage", mapOf("input_tokens", 0, "output_tokens", 0));

        Map<String, Object> startEvent = new LinkedHashMap<>();
        startEvent.put("type", "message_start");
        startEvent.put("message", startMsg);
        callback.onEvent(sseEncode("message_start", startEvent));

        BufferedReader reader = new BufferedReader(new InputStreamReader(upstreamStream, StandardCharsets.UTF_8));
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.isEmpty()) continue;
            if (!line.startsWith("data: ")) continue;

            String dataStr = line.substring(6).trim();
            if ("[DONE]".equals(dataStr)) break;

            Map<String, Object> chunk;
            try {
                chunk = mapper.readValue(dataStr, Map.class);
            } catch (Exception e) {
                continue;
            }

            Map<String, Object> chunkUsage = (Map<String, Object>) chunk.get("usage");
            if (chunkUsage != null) {
                inputTokens = toInt(chunkUsage.get("prompt_tokens"), inputTokens);
                outputTokens = toInt(chunkUsage.get("completion_tokens"), outputTokens);
            }

            List<Map<String, Object>> choices = (List<Map<String, Object>>) chunk.get("choices");
            if (choices == null || choices.isEmpty()) continue;

            Map<String, Object> choice = choices.get(0);
            Map<String, Object> delta = (Map<String, Object>) choice.getOrDefault("delta", new HashMap<>());
            String chunkFinish = (String) choice.get("finish_reason");
            if (chunkFinish != null) finishReason = chunkFinish;

            String reasoningText = (String) delta.getOrDefault("reasoning_content", "");
            if (reasoningText != null && !reasoningText.isEmpty()) {
                if (thinkingBlockIndex < 0) {
                    thinkingBlockIndex = nextBlockIndex++;
                    Map<String, Object> block = new LinkedHashMap<>();
                    block.put("type", "thinking");
                    block.put("thinking", "");
                    block.put("signature", "");
                    callback.onEvent(sseBlockStart(thinkingBlockIndex, block));
                }
                Map<String, Object> d = new LinkedHashMap<>();
                d.put("type", "thinking_delta");
                d.put("thinking", reasoningText);
                callback.onEvent(sseDelta(thinkingBlockIndex, d));
            }

            String contentText = (String) delta.getOrDefault("content", "");
            if (contentText != null && !contentText.isEmpty()) {
                if (thinkingBlockIndex >= 0 && !closedBlocks.contains(thinkingBlockIndex)) {
                    callback.onEvent(sseStop(thinkingBlockIndex));
                    closedBlocks.add(thinkingBlockIndex);
                }
                if (textBlockIndex < 0) {
                    textBlockIndex = nextBlockIndex++;
                    callback.onEvent(sseBlockStart(textBlockIndex, mapOf("type", "text", "text", "")));
                }
                Map<String, Object> d = new LinkedHashMap<>();
                d.put("type", "text_delta");
                d.put("text", contentText);
                callback.onEvent(sseDelta(textBlockIndex, d));
            }

            List<Map<String, Object>> tcDeltas = (List<Map<String, Object>>) delta.get("tool_calls");
            if (tcDeltas != null) {
                for (Map<String, Object> tc : tcDeltas) {
                    int tcIdx = toInt(tc.get("index"), 0);
                    if (!tcIndexMap.containsKey(tcIdx)) {
                        tcIndexMap.put(tcIdx, nextBlockIndex++);
                        String tcId = str(tc.get("id"), "");
                        Map<String, Object> func = (Map<String, Object>) tc.getOrDefault("function", new HashMap<>());
                        String tcName = str(func.get("name"), "");
                        Map<String, Object> block = new LinkedHashMap<>();
                        block.put("type", "tool_use");
                        block.put("id", tcId);
                        block.put("name", tcName);
                        block.put("input", new HashMap<>());
                        callback.onEvent(sseBlockStart(tcIndexMap.get(tcIdx), block));
                    }
                    Map<String, Object> func = (Map<String, Object>) tc.getOrDefault("function", new HashMap<>());
                    String args = str(func.get("arguments"), "");
                    if (!args.isEmpty()) {
                        Map<String, Object> d = new LinkedHashMap<>();
                        d.put("type", "input_json_delta");
                        d.put("partial_json", args);
                        callback.onEvent(sseDelta(tcIndexMap.get(tcIdx), d));
                    }
                }
            }
        }

        for (int i = 0; i < nextBlockIndex; i++) {
            if (!closedBlocks.contains(i)) {
                callback.onEvent(sseStop(i));
            }
        }

        String anthropicStop = finishReason != null ? FINISH_REASON_MAP.getOrDefault(finishReason, "end_turn") : "end_turn";

        Map<String, Object> msgDelta = new LinkedHashMap<>();
        msgDelta.put("type", "message_delta");
        Map<String, Object> deltaBody = new LinkedHashMap<>();
        deltaBody.put("stop_reason", anthropicStop);
        deltaBody.put("stop_sequence", null);
        msgDelta.put("delta", deltaBody);
        msgDelta.put("usage", mapOf("output_tokens", outputTokens));
        callback.onEvent(sseEncode("message_delta", msgDelta));

        Map<String, Object> msgStop = new LinkedHashMap<>();
        msgStop.put("type", "message_stop");
        callback.onEvent(sseEncode("message_stop", msgStop));
    }

    private String sseBlockStart(int index, Map<String, Object> block) {
        Map<String, Object> evt = new LinkedHashMap<>();
        evt.put("type", "content_block_start");
        evt.put("index", index);
        evt.put("content_block", block);
        return sseEncode("content_block_start", evt);
    }

    private String sseDelta(int index, Map<String, Object> delta) {
        Map<String, Object> evt = new LinkedHashMap<>();
        evt.put("type", "content_block_delta");
        evt.put("index", index);
        evt.put("delta", delta);
        return sseEncode("content_block_delta", evt);
    }

    private String sseStop(int index) {
        Map<String, Object> evt = new LinkedHashMap<>();
        evt.put("type", "content_block_stop");
        evt.put("index", index);
        return sseEncode("content_block_stop", evt);
    }

    private String sseEncode(String eventType, Map<String, Object> data) {
        try {
            String json = mapper.writeValueAsString(data);
            return "event: " + eventType + "\ndata: " + json + "\n\n";
        } catch (JsonProcessingException e) {
            log.error("Failed to encode SSE event: {}", e.getMessage());
            return "";
        }
    }

    private static String str(Object v, String def) {
        return v != null ? v.toString() : def;
    }

    private static int toInt(Object v, int def) {
        if (v instanceof Number) return ((Number) v).intValue();
        return def;
    }

    private static Map<String, Object> mapOf(String k1, Object v1) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k1, v1);
        return m;
    }

    private static Map<String, Object> mapOf(String k1, Object v1, String k2, Object v2) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put(k1, v1);
        m.put(k2, v2);
        return m;
    }

    public interface SseCallback {
        void onEvent(String event);
    }
}