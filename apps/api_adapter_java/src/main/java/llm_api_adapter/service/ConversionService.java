package llm_api_adapter.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import llm_api_adapter.model.AnthropicRequest;
import llm_api_adapter.model.AnthropicResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class ConversionService {
    private static final Logger log = LoggerFactory.getLogger(ConversionService.class);

    private static final Map<String, String> FINISH_REASON_MAP = new HashMap<>();
    static {
        FINISH_REASON_MAP.put("stop", "end_turn");
        FINISH_REASON_MAP.put("length", "max_tokens");
        FINISH_REASON_MAP.put("tool_calls", "tool_use");
        FINISH_REASON_MAP.put("content_filter", "end_turn");
    }

    private final ObjectMapper mapper = new ObjectMapper();

    public Map<String, Object> anthropicToOpenAIRequest(AnthropicRequest req, String llmModelName) {
        Map<String, Object> oaiReq = new LinkedHashMap<>();
        oaiReq.put("model", llmModelName);
        oaiReq.put("messages", anthropicToOpenAIMessages(req.getMessages(), req.getSystem()));
        oaiReq.put("max_tokens", req.getMaxTokens() != null ? req.getMaxTokens() : 4096);
        oaiReq.put("temperature", req.getTemperature() != null ? req.getTemperature() : 0.7);
        boolean stream = req.getStream() != null && req.getStream();
        oaiReq.put("stream", stream);

        if (req.getStopSequences() != null && !req.getStopSequences().isEmpty()) {
            oaiReq.put("stop", req.getStopSequences());
        }
        if (req.getTopP() != null) {
            oaiReq.put("top_p", req.getTopP());
        }

        if (req.getTools() != null && !req.getTools().isEmpty()) {
            List<Map<String, Object>> oaiTools = new ArrayList<>();
            for (Map<String, Object> t : req.getTools()) {
                Map<String, Object> func = new LinkedHashMap<>();
                func.put("name", str(t.get("name"), ""));
                func.put("description", str(t.get("description"), ""));
                Object schema = t.get("input_schema");
                if (schema == null) schema = new LinkedHashMap<>();
                func.put("parameters", schema);
                Map<String, Object> oaiTool = new LinkedHashMap<>();
                oaiTool.put("type", "function");
                oaiTool.put("function", func);
                oaiTools.add(oaiTool);
            }
            oaiReq.put("tools", oaiTools);
        }

        if (req.getToolChoice() != null) {
            String tcType = str(req.getToolChoice().get("type"), "auto");
            switch (tcType) {
                case "any":
                    oaiReq.put("tool_choice", "required");
                    break;
                case "tool": {
                    String name = str(req.getToolChoice().get("name"), null);
                    if (name != null) {
                        Map<String, Object> tc = new LinkedHashMap<>();
                        tc.put("type", "function");
                        Map<String, Object> fn = new LinkedHashMap<>();
                        fn.put("name", name);
                        tc.put("function", fn);
                        oaiReq.put("tool_choice", tc);
                    }
                    break;
                }
                default:
                    oaiReq.put("tool_choice", "auto");
            }
        }

        if (req.getMetadata() != null && req.getMetadata().containsKey("user_id")) {
            oaiReq.put("user", req.getMetadata().get("user_id"));
        }

        if (req.getThinking() != null) {
            log.info("ignoring Anthropic 'thinking' parameter (not supported)");
        }
        if (req.getTopK() != null) {
            log.warn("ignoring Anthropic 'top_k' parameter");
        }

        return oaiReq;
    }

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> anthropicToOpenAIMessages(List<Map<String, Object>> anthropicMessages,
                                                                 Object systemPrompt) {
        List<Map<String, Object>> result = new ArrayList<>();

        if (systemPrompt != null) {
            String systemText = null;
            if (systemPrompt instanceof List) {
                StringBuilder sb = new StringBuilder();
                for (Object block : (List<?>) systemPrompt) {
                    if (block instanceof Map) {
                        Map<String, Object> m = (Map<String, Object>) block;
                        if ("text".equals(m.get("type"))) {
                            sb.append(m.get("text"));
                        }
                    }
                }
                systemText = sb.toString();
            } else if (systemPrompt instanceof String) {
                systemText = (String) systemPrompt;
            }
            if (systemText != null && !systemText.isEmpty()) {
                Map<String, Object> sysMsg = new LinkedHashMap<>();
                sysMsg.put("role", "system");
                sysMsg.put("content", systemText);
                result.add(sysMsg);
            }
        }

        if (anthropicMessages == null) return result;

        for (Map<String, Object> msg : anthropicMessages) {
            String role = str(msg.get("role"), "");
            Object content = msg.get("content");

            if ("user".equals(role)) {
                result.addAll(convertUserContent(content));
            } else if ("assistant".equals(role)) {
                result.add(convertAssistantContent(content));
            }
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> convertUserContent(Object content) {
        if (content instanceof String) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("role", "user");
            m.put("content", content);
            return Collections.singletonList(m);
        }
        if (content instanceof List) {
            List<?> blocks = (List<?>) content;
            List<String> textParts = new ArrayList<>();
            List<Map<String, Object>> imageParts = new ArrayList<>();
            List<Map<String, Object>> toolMessages = new ArrayList<>();

            for (Object b : blocks) {
                if (!(b instanceof Map)) continue;
                Map<String, Object> block = (Map<String, Object>) b;
                String type = str(block.get("type"), "");
                if ("text".equals(type)) {
                    textParts.add(str(block.get("text"), ""));
                } else if ("image".equals(type)) {
                    Map<String, Object> source = (Map<String, Object>) block.get("source");
                    String mediaType = str(source != null ? source.get("media_type") : null, "image/png");
                    String data = str(source != null ? source.get("data") : null, "");
                    Map<String, Object> img = new LinkedHashMap<>();
                    img.put("type", "image_url");
                    Map<String, Object> url = new LinkedHashMap<>();
                    url.put("url", "data:" + mediaType + ";base64," + data);
                    img.put("image_url", url);
                    imageParts.add(img);
                } else if ("tool_result".equals(type)) {
                    String toolUseId = str(block.get("tool_use_id"), "");
                    Object tc = block.get("content");
                    String toolText;
                    if (tc instanceof List) {
                        StringBuilder sb = new StringBuilder();
                        for (Object tcb : (List<?>) tc) {
                            if (tcb instanceof Map) {
                                Map<String, Object> m = (Map<String, Object>) tcb;
                                if ("text".equals(m.get("type"))) {
                                    sb.append(m.get("text"));
                                }
                            }
                        }
                        toolText = sb.toString();
                    } else {
                        toolText = tc != null ? tc.toString() : "";
                    }
                    Map<String, Object> tm = new LinkedHashMap<>();
                    tm.put("role", "tool");
                    tm.put("tool_call_id", toolUseId);
                    tm.put("content", toolText);
                    toolMessages.add(tm);
                }
            }

            List<Map<String, Object>> msgs = new ArrayList<>();
            if (!textParts.isEmpty() || !imageParts.isEmpty()) {
                Map<String, Object> userMsg = new LinkedHashMap<>();
                userMsg.put("role", "user");
                if (imageParts.isEmpty()) {
                    userMsg.put("content", join("\n", textParts));
                } else if (textParts.isEmpty()) {
                    userMsg.put("content", imageParts);
                } else {
                    List<Object> combined = new ArrayList<>();
                    Map<String, Object> textBlock = new LinkedHashMap<>();
                    textBlock.put("type", "text");
                    textBlock.put("text", join("\n", textParts));
                    combined.add(textBlock);
                    combined.addAll(imageParts);
                    userMsg.put("content", combined);
                }
                msgs.add(userMsg);
            }
            msgs.addAll(toolMessages);
            return msgs;
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("role", "user");
        m.put("content", content != null ? content.toString() : "");
        return Collections.singletonList(m);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> convertAssistantContent(Object content) {
        if (content instanceof String) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("role", "assistant");
            m.put("content", content);
            return m;
        }
        if (content instanceof List) {
            List<?> blocks = (List<?>) content;
            StringBuilder textParts = new StringBuilder();
            List<Map<String, Object>> toolCalls = new ArrayList<>();

            for (Object b : blocks) {
                if (!(b instanceof Map)) continue;
                Map<String, Object> block = (Map<String, Object>) b;
                String type = str(block.get("type"), "");
                if ("text".equals(type)) {
                    if (textParts.length() > 0) textParts.append("\n");
                    textParts.append(str(block.get("text"), ""));
                } else if ("tool_use".equals(type)) {
                    Map<String, Object> func = new LinkedHashMap<>();
                    func.put("name", str(block.get("name"), ""));
                    try {
                        func.put("arguments", mapper.writeValueAsString(block.getOrDefault("input", "")));
                    } catch (JsonProcessingException e) {
                        func.put("arguments", "{}");
                    }
                    Map<String, Object> tc = new LinkedHashMap<>();
                    tc.put("id", str(block.get("id"), ""));
                    tc.put("type", "function");
                    tc.put("function", func);
                    toolCalls.add(tc);
                }
            }

            Map<String, Object> oai = new LinkedHashMap<>();
            oai.put("role", "assistant");
            oai.put("content", textParts.toString());
            if (!toolCalls.isEmpty()) {
                oai.put("tool_calls", toolCalls);
            }
            return oai;
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("role", "assistant");
        m.put("content", content != null ? content.toString() : "");
        return m;
    }

    @SuppressWarnings("unchecked")
    public AnthropicResponse openAIToAnthropicResponse(Map<String, Object> openaiResponse,
                                                        String anthropicModel,
                                                        String requestId) {
        AnthropicResponse resp = new AnthropicResponse();
        resp.setId(requestId != null ? requestId : "msg_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        resp.setType("message");
        resp.setRole("assistant");
        resp.setModel(anthropicModel);

        List<Map<String, Object>> choices = (List<Map<String, Object>>) openaiResponse.getOrDefault("choices", Collections.emptyList());
        Map<String, Object> choice = choices.isEmpty() ? new HashMap<String, Object>() : choices.get(0);
        Map<String, Object> message = (Map<String, Object>) choice.getOrDefault("message", new HashMap<String, Object>());

        String contentText = str(message.get("content"), "");
        String reasoningText = str(message.get("reasoning_content"), "");
        String finishReason = str(choice.get("finish_reason"), "stop");
        String stopReason = FINISH_REASON_MAP.getOrDefault(finishReason, "end_turn");
        resp.setStopReason(stopReason);
        resp.setStopSequence(null);

        Map<String, Object> usage = (Map<String, Object>) openaiResponse.getOrDefault("usage", new HashMap<String, Object>());
        AnthropicResponse.Usage u = new AnthropicResponse.Usage();
        u.setInputTokens(toInt(usage.get("prompt_tokens"), 0));
        u.setOutputTokens(toInt(usage.get("completion_tokens"), 0));
        resp.setUsage(u);

        List<AnthropicResponse.ContentBlock> blocks = new ArrayList<>();

        if (reasoningText != null && !reasoningText.isEmpty()) {
            AnthropicResponse.ContentBlock tb = new AnthropicResponse.ContentBlock();
            tb.setType("thinking");
            tb.setThinking(reasoningText);
            tb.setSignature("");
            blocks.add(tb);
        }
        if (contentText != null && !contentText.isEmpty()) {
            AnthropicResponse.ContentBlock cb = new AnthropicResponse.ContentBlock();
            cb.setType("text");
            cb.setText(contentText);
            blocks.add(cb);
        }

        List<Map<String, Object>> toolCalls = (List<Map<String, Object>>) message.getOrDefault("tool_calls", Collections.emptyList());
        for (Map<String, Object> tc : toolCalls) {
            Map<String, Object> func = (Map<String, Object>) tc.getOrDefault("function", new HashMap<String, Object>());
            Object args = func.getOrDefault("arguments", "{}");
            Object parsed;
            try {
                parsed = mapper.readValue(args.toString(), Object.class);
            } catch (Exception e) {
                Map<String, Object> fallback = new HashMap<>();
                fallback.put("arguments", args.toString());
                parsed = fallback;
            }
            AnthropicResponse.ContentBlock tb = new AnthropicResponse.ContentBlock();
            tb.setType("tool_use");
            tb.setId(str(tc.get("id"), ""));
            tb.setName(str(func.get("name"), ""));
            tb.setInput(parsed);
            blocks.add(tb);
        }

        resp.setContent(blocks);
        return resp;
    }

    // ── helpers ──

    private static String str(Object v, String def) {
        return v != null ? v.toString() : def;
    }

    private static int toInt(Object v, int def) {
        if (v instanceof Number) return ((Number) v).intValue();
        if (v instanceof String) try { return Integer.parseInt((String) v); } catch (Exception ignored) {}
        return def;
    }

    private static String join(String delimiter, List<String> parts) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < parts.size(); i++) {
            if (i > 0) sb.append(delimiter);
            sb.append(parts.get(i));
        }
        return sb.toString();
    }
}