package llm_api_adapter.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import llm_api_adapter.config.AppConfig;
import llm_api_adapter.model.AnthropicRequest;
import llm_api_adapter.model.AnthropicResponse;
import llm_api_adapter.model.ErrorResponse;
import llm_api_adapter.service.ConversionService;
import llm_api_adapter.service.SseConversionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.*;

@RestController
public class ApiController {
    private static final Logger log = LoggerFactory.getLogger(ApiController.class);

    @Autowired
    private AppConfig appConfig;
    @Autowired
    private ConversionService conversionService;
    @Autowired
    private SseConversionService sseConversionService;

    private final ObjectMapper mapper = new ObjectMapper();

    // ── health / root ──

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", "healthy");
        m.put("adapter", "openai-to-anthropic");
        m.put("upstream_model", appConfig.getLlmModelName());
        m.put("upstream_uri", appConfig.getLlmApiUri());
        m.put("timestamp", System.currentTimeMillis() / 1000);
        return m;
    }

    @GetMapping("/")
    public Map<String, Object> welcome() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", 200);
        m.put("msg", "LLM API Adapter - OpenAI to Anthropic API converter");
        m.put("upstream_model", appConfig.getLlmModelName());
        m.put("upstream_uri", appConfig.getLlmApiUri());
        m.put("anthropic_api_version", "2023-06-01");
        Map<String, String> endpoints = new LinkedHashMap<>();
        endpoints.put("messages", "/v1/messages");
        endpoints.put("models", "/v1/models");
        endpoints.put("health", "/health");
        m.put("endpoints", endpoints);
        m.put("timestamp", System.currentTimeMillis() / 1000);
        return m;
    }

    // ── models ──

    @GetMapping("/v1/models")
    public Map<String, Object> listModels() {
        String model = appConfig.getLlmModelName();
        Map<String, Object> data = new LinkedHashMap<>();
        Map<String, Object> modelItem = new LinkedHashMap<>();
        modelItem.put("id", model);
        modelItem.put("type", "model");
        modelItem.put("display_name", model);
        modelItem.put("created_at", "2024-01-01T00:00:00Z");
        List<Map<String, Object>> list = new ArrayList<>();
        list.add(modelItem);
        data.put("data", list);
        data.put("has_more", false);
        data.put("first_id", model);
        data.put("last_id", model);
        return data;
    }

    @GetMapping("/v1/models/{modelId}")
    public Map<String, Object> getModel(@PathVariable String modelId) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", modelId);
        m.put("type", "model");
        m.put("display_name", modelId);
        m.put("created_at", "2024-01-01T00:00:00Z");
        return m;
    }

    // ── messages ──

    @PostMapping("/v1/messages")
    public ResponseEntity<?> createMessage(@RequestBody AnthropicRequest req,
                                            HttpServletRequest httpReq,
                                            HttpServletResponse httpResp) {
        long start = System.currentTimeMillis();

        ResponseEntity<?> authErr = checkAuth(httpReq);
        if (authErr != null) return authErr;

        if (req.getMessages() == null || req.getMessages().isEmpty()) {
            return ResponseEntity.status(400).body(
                    new ErrorResponse("error", "invalid_request_error", "messages must be a non-empty list"));
        }

        boolean stream = req.getStream() != null && req.getStream();
        String anthropicModel = req.getModel() != null ? req.getModel() : appConfig.getLlmModelName();

        try {
            if (stream) {
                Map<String, Object> openaiReq = conversionService.anthropicToOpenAIRequest(req, appConfig.getLlmModelName());
                handleStream(openaiReq, anthropicModel, httpResp);
                return null; // response already committed
            } else {
                Map<String, Object> openaiReq = conversionService.anthropicToOpenAIRequest(req, appConfig.getLlmModelName());
                return handleNonStream(openaiReq, anthropicModel, start);
            }
        } catch (Exception e) {
            log.error("Unexpected error", e);
            return ResponseEntity.status(500).body(
                    new ErrorResponse("error", "internal_error", e.getMessage()));
        }
    }

    // ── count_tokens ──

    @SuppressWarnings("unchecked")
    @PostMapping("/v1/messages/count_tokens")
    public ResponseEntity<?> countTokens(@RequestBody Map<String, Object> body,
                                          HttpServletRequest httpReq) {
        ResponseEntity<?> authErr = checkAuth(httpReq);
        if (authErr != null) return authErr;

        List<Map<String, Object>> messages = (List<Map<String, Object>>) body.getOrDefault("messages", new ArrayList<>());
        Object system = body.get("system");
        String systemText = "";
        if (system instanceof List) {
            StringBuilder sb = new StringBuilder();
            for (Object s : (List<?>) system) {
                if (s instanceof Map) {
                    Map<String, Object> m = (Map<String, Object>) s;
                    if ("text".equals(m.get("type"))) {
                        sb.append(m.get("text"));
                    }
                }
            }
            systemText = sb.toString();
        } else if (system instanceof String) {
            systemText = (String) system;
        }
        Object tools = body.get("tools");
        String toolStr = tools != null ? tools.toString() : "";
        int totalChars = systemText.length() + messages.toString().length() + toolStr.length();
        int inputTokens = Math.max(totalChars / 3, 1);
        Map<String, Integer> result = new HashMap<>();
        result.put("input_tokens", inputTokens);
        return ResponseEntity.ok(result);
    }

    // ── private ──

    private ResponseEntity<?> checkAuth(HttpServletRequest req) {
        String apiKey = appConfig.getLlmApiKey();
        if (apiKey == null || apiKey.isEmpty() || apiKey.equals("sk-123456")) return null;

        String provided = req.getHeader("x-api-key");
        if (provided == null) {
            String auth = req.getHeader("Authorization");
            if (auth != null && auth.startsWith("Bearer ")) {
                provided = auth.substring(7);
            }
        }
        if (provided == null || !provided.equals(apiKey)) {
            log.warn("Invalid API key attempt");
            return ResponseEntity.status(401).body(
                    new ErrorResponse("error", "authentication_error", "invalid api key"));
        }
        return null;
    }

    private void handleStream(Map<String, Object> openaiReq, String anthropicModel,
                               HttpServletResponse httpResp) throws Exception {

        String bodyJson = mapper.writeValueAsString(openaiReq);
        log.info("forward to {}/chat/completions, model={}, stream=true",
                appConfig.getLlmApiUri(), appConfig.getLlmModelName());

        URL url = new URL(appConfig.getLlmApiUri() + "/chat/completions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("Authorization", "Bearer " + appConfig.getLlmApiKey());
        conn.setDoOutput(true);
        conn.setConnectTimeout(30000);
        conn.setReadTimeout(300000);

        try (OutputStream os = conn.getOutputStream()) {
            os.write(bodyJson.getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        int statusCode = conn.getResponseCode();
        if (statusCode != 200) {
            String errBody = new String(readAll(conn.getErrorStream()), StandardCharsets.UTF_8);
            log.error("Upstream error: {} - {}", statusCode, errBody);
            httpResp.setStatus(502);
            httpResp.setContentType("application/json;charset=UTF-8");
            mapper.writeValue(httpResp.getOutputStream(),
                    new ErrorResponse("error", "api_error", "Upstream API returned " + statusCode));
            return;
        }

        httpResp.setContentType("text/event-stream");
        httpResp.setCharacterEncoding("UTF-8");
        httpResp.setHeader("Cache-Control", "no-cache");
        httpResp.setHeader("Connection", "keep-alive");
        httpResp.setHeader("x-request-id", "msg_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));

        OutputStream out = httpResp.getOutputStream();
        sseConversionService.convertStream(conn.getInputStream(), anthropicModel, new SseConversionService.SseCallback() {
            @Override
            public void onEvent(String event) {
                try {
                    out.write(event.getBytes(StandardCharsets.UTF_8));
                    out.flush();
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            }
        });
        out.close();
    }

    private ResponseEntity<?> handleNonStream(Map<String, Object> openaiReq,
                                               String anthropicModel,
                                               long start) throws Exception {
        String bodyJson = mapper.writeValueAsString(openaiReq);
        log.info("forward to {}/chat/completions, model={}, stream=false",
                appConfig.getLlmApiUri(), appConfig.getLlmModelName());

        URL url = new URL(appConfig.getLlmApiUri() + "/chat/completions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("Authorization", "Bearer " + appConfig.getLlmApiKey());
        conn.setDoOutput(true);
        conn.setConnectTimeout(30000);
        conn.setReadTimeout(300000);

        try (OutputStream os = conn.getOutputStream()) {
            os.write(bodyJson.getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        int statusCode = conn.getResponseCode();
        if (statusCode != 200) {
            String errBody = new String(readAll(conn.getErrorStream()), StandardCharsets.UTF_8);
            log.error("Upstream error: {} - {}", statusCode, errBody);
            return ResponseEntity.status(502).body(
                    new ErrorResponse("error", "api_error", "Upstream API returned " + statusCode));
        }

        String responseBody = new String(readAll(conn.getInputStream()), StandardCharsets.UTF_8);
        @SuppressWarnings("unchecked")
        Map<String, Object> openaiResponse = mapper.readValue(responseBody, Map.class);
        AnthropicResponse anthropicResp = conversionService.openAIToAnthropicResponse(
                openaiResponse, anthropicModel, null);

        long elapsed = (System.currentTimeMillis() - start) / 1000;
        log.info("Request processed in {}s, stream=false", elapsed);

        return ResponseEntity.ok()
                .header("x-request-id", anthropicResp.getId())
                .body(anthropicResp);
    }

    private static byte[] readAll(java.io.InputStream in) throws java.io.IOException {
        java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
        byte[] tmp = new byte[4096];
        int n;
        while ((n = in.read(tmp)) != -1) {
            buffer.write(tmp, 0, n);
        }
        return buffer.toByteArray();
    }

    // Global exception handler
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleException(Exception e) {
        log.error("Unhandled exception", e);
        return ResponseEntity.status(500).body(
                new ErrorResponse("error", "internal_error", e.getMessage()));
    }
}