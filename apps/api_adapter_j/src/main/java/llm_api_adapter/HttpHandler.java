package llm_api_adapter;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.*;
import io.netty.handler.codec.http.*;
import io.netty.handler.codec.http.cors.CorsConfig;
import io.netty.handler.codec.http.cors.CorsConfigBuilder;
import io.netty.handler.codec.http.cors.CorsHandler;
import io.netty.util.CharsetUtil;
import llm_api_adapter.config.Config;
import llm_api_adapter.model.AnthropicRequest;
import llm_api_adapter.model.AnthropicResponse;
import llm_api_adapter.model.ErrorResponse;
import llm_api_adapter.service.ConversionService;
import llm_api_adapter.service.SseConversionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.net.ssl.*;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyManagementException;
import java.security.NoSuchAlgorithmException;
import java.security.cert.X509Certificate;
import java.util.*;

import static io.netty.handler.codec.http.HttpResponseStatus.*;
import static io.netty.handler.codec.http.HttpVersion.HTTP_1_1;

public class HttpHandler extends SimpleChannelInboundHandler<FullHttpRequest> {

    private static final Logger log = LoggerFactory.getLogger(HttpHandler.class);

    private final Config cfg;
    private final ObjectMapper mapper = new ObjectMapper();
    private final ConversionService conversionService = new ConversionService();
    private final SseConversionService sseConversionService = new SseConversionService();

    static {
        // Disable SSL verification for upstream requests (internal/corporate servers)
        try {
            TrustManager[] trustAll = new TrustManager[]{
                    new X509TrustManager() {
                        public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
                        public void checkClientTrusted(X509Certificate[] certs, String authType) {}
                        public void checkServerTrusted(X509Certificate[] certs, String authType) {}
                    }
            };
            SSLContext sc = SSLContext.getInstance("TLS");
            sc.init(null, trustAll, new java.security.SecureRandom());
            HttpsURLConnection.setDefaultSSLSocketFactory(sc.getSocketFactory());
            HttpsURLConnection.setDefaultHostnameVerifier((hostname, session) -> true);
        } catch (KeyManagementException | NoSuchAlgorithmException e) {
            throw new RuntimeException("Failed to disable SSL verification", e);
        }
    }

    public HttpHandler(Config cfg) {
        this.cfg = cfg;
    }

    // ── CORS config per-channel ──

    public static CorsConfig corsConfig() {
        return CorsConfigBuilder.forAnyOrigin()
                .allowedRequestHeaders("Content-Type", "Authorization", "x-api-key", "anthropic-version")
                .allowedRequestMethods(io.netty.handler.codec.http.HttpMethod.GET,
                        io.netty.handler.codec.http.HttpMethod.POST,
                        io.netty.handler.codec.http.HttpMethod.OPTIONS)
                .allowNullOrigin()
                .allowCredentials()
                .build();
    }

    // ── dispatch ──

    @Override
    protected void channelRead0(ChannelHandlerContext ctx, FullHttpRequest req) {
        String uri = req.uri();
        io.netty.handler.codec.http.HttpMethod method = req.method();

        // OPTIONS handled by Netty CorsHandler already — but belt-and-suspenders
        if (method == io.netty.handler.codec.http.HttpMethod.OPTIONS) {
            writeNoContent(ctx);
            return;
        }

        if (method == io.netty.handler.codec.http.HttpMethod.GET) {
            if ("/health".equals(uri)) {
                handleHealth(ctx);
            } else if ("/".equals(uri)) {
                handleWelcome(ctx);
            } else if ("/v1/models".equals(uri)) {
                handleListModels(ctx);
            } else if (uri.startsWith("/v1/models/")) {
                String modelId = uri.substring("/v1/models/".length());
                handleGetModel(ctx, modelId);
            } else {
                writeError(ctx, NOT_FOUND, "invalid_request_error", "not found");
            }
            return;
        }

        if (method == io.netty.handler.codec.http.HttpMethod.POST) {
            if ("/v1/messages".equals(uri)) {
                handleCreateMessage(ctx, req);
            } else if ("/v1/messages/count_tokens".equals(uri)) {
                handleCountTokens(ctx, req);
            } else {
                writeError(ctx, NOT_FOUND, "invalid_request_error", "not found");
            }
            return;
        }

        writeError(ctx, METHOD_NOT_ALLOWED, "invalid_request_error", "method not allowed");
    }

    // ── GET handlers ──

    private void handleHealth(ChannelHandlerContext ctx) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", "healthy");
        m.put("adapter", "openai-to-anthropic");
        m.put("upstream_model", cfg.getLlmModelName());
        m.put("upstream_uri", cfg.getLlmApiUri());
        m.put("timestamp", System.currentTimeMillis() / 1000);
        writeJson(ctx, OK, m);
    }

    private void handleWelcome(ChannelHandlerContext ctx) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", 200);
        m.put("msg", "LLM API Adapter - OpenAI to Anthropic API converter");
        m.put("upstream_model", cfg.getLlmModelName());
        m.put("upstream_uri", cfg.getLlmApiUri());
        m.put("anthropic_api_version", "2023-06-01");
        Map<String, String> eps = new LinkedHashMap<>();
        eps.put("messages", "/v1/messages");
        eps.put("models", "/v1/models");
        eps.put("health", "/health");
        m.put("endpoints", eps);
        m.put("timestamp", System.currentTimeMillis() / 1000);
        writeJson(ctx, OK, m);
    }

    private void handleListModels(ChannelHandlerContext ctx) {
        String model = cfg.getLlmModelName();
        Map<String, Object> data = new LinkedHashMap<>();
        List<Map<String, Object>> list = new ArrayList<>();
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", model);
        item.put("type", "model");
        item.put("display_name", model);
        item.put("created_at", "2024-01-01T00:00:00Z");
        list.add(item);
        data.put("data", list);
        data.put("has_more", false);
        data.put("first_id", model);
        data.put("last_id", model);
        writeJson(ctx, OK, data);
    }

    private void handleGetModel(ChannelHandlerContext ctx, String modelId) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", modelId);
        m.put("type", "model");
        m.put("display_name", modelId);
        m.put("created_at", "2024-01-01T00:00:00Z");
        writeJson(ctx, OK, m);
    }

    // ── POST handlers ──

    private void handleCreateMessage(ChannelHandlerContext ctx, FullHttpRequest req) {
        long start = System.currentTimeMillis();

        String body = req.content().toString(CharsetUtil.UTF_8);
        AnthropicRequest data;
        try {
            data = mapper.readValue(body, AnthropicRequest.class);
        } catch (Exception e) {
            writeError(ctx, BAD_REQUEST, "invalid_request_error", "invalid JSON in request body");
            return;
        }

        if (data.getMessages() == null || data.getMessages().isEmpty()) {
            writeError(ctx, BAD_REQUEST, "invalid_request_error", "messages must be a non-empty list");
            return;
        }

        boolean stream = data.getStream() != null && data.getStream();
        String anthropicModel = data.getModel() != null ? data.getModel() : cfg.getLlmModelName();

        Map<String, Object> openaiReq = conversionService.anthropicToOpenAIRequest(data, cfg.getLlmModelName());

        try {
            if (stream) {
                handleStream(ctx, openaiReq, anthropicModel, start);
            } else {
                handleNonStream(ctx, openaiReq, anthropicModel, start);
            }
        } catch (Exception e) {
            log.error("Unexpected error", e);
            writeError(ctx, INTERNAL_SERVER_ERROR, "internal_error", e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private void handleCountTokens(ChannelHandlerContext ctx, FullHttpRequest req) {
        String body = req.content().toString(CharsetUtil.UTF_8);
        Map<String, Object> data;
        try {
            data = mapper.readValue(body, Map.class);
        } catch (Exception e) {
            writeError(ctx, BAD_REQUEST, "invalid_request_error", "invalid JSON");
            return;
        }

        List<Map<String, Object>> messages = (List<Map<String, Object>>) data.getOrDefault("messages", new ArrayList<>());
        Object system = data.get("system");
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
        Object tools = data.get("tools");
        String toolStr = tools != null ? tools.toString() : "";
        int totalChars = systemText.length() + messages.toString().length() + toolStr.length();
        int inputTokens = Math.max(totalChars / 3, 1);
        Map<String, Integer> result = new HashMap<>();
        result.put("input_tokens", inputTokens);
        writeJson(ctx, OK, result);
    }

    // ── upstream proxy ──

    private void handleNonStream(ChannelHandlerContext ctx, Map<String, Object> openaiReq,
                                  String anthropicModel, long start) throws Exception {
        String bodyJson = mapper.writeValueAsString(openaiReq);
        String upstreamUrl = stripTrailingSlash(cfg.getLlmApiUri()) + "/chat/completions";
        log.info("forward to {}, model={}, stream=false", upstreamUrl, cfg.getLlmModelName());

        HttpURLConnection conn = openConnection(upstreamUrl);
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("Authorization", "Bearer " + cfg.getLlmApiKey());
        try (OutputStream os = conn.getOutputStream()) {
            os.write(bodyJson.getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        int statusCode = conn.getResponseCode();
        if (statusCode != 200) {
            String errBody = readStream(conn.getErrorStream());
            log.error("Upstream error: {} - {}", statusCode, errBody);
            writeError(ctx, BAD_GATEWAY, "api_error", "Upstream API returned " + statusCode);
            return;
        }

        String responseBody = readStream(conn.getInputStream());
        @SuppressWarnings("unchecked")
        Map<String, Object> openaiResponse = mapper.readValue(responseBody, Map.class);
        AnthropicResponse anthropicResp = conversionService.openAIToAnthropicResponse(openaiResponse, anthropicModel, null);

        long elapsed = (System.currentTimeMillis() - start) / 1000;
        log.info("Request processed in {}s, stream=false", elapsed);

        writeJson(ctx, OK, anthropicResp, Collections.singletonMap("x-request-id", anthropicResp.getId()));
    }

    private void handleStream(ChannelHandlerContext ctx, Map<String, Object> openaiReq,
                               String anthropicModel, long start) throws Exception {
        String bodyJson = mapper.writeValueAsString(openaiReq);
        String upstreamUrl = stripTrailingSlash(cfg.getLlmApiUri()) + "/chat/completions";
        log.info("forward to {}, model={}, stream=true", upstreamUrl, cfg.getLlmModelName());

        HttpURLConnection conn = openConnection(upstreamUrl);
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setRequestProperty("Authorization", "Bearer " + cfg.getLlmApiKey());
        try (OutputStream os = conn.getOutputStream()) {
            os.write(bodyJson.getBytes(StandardCharsets.UTF_8));
            os.flush();
        }

        int statusCode = conn.getResponseCode();
        if (statusCode != 200) {
            String errBody = readStream(conn.getErrorStream());
            log.error("Upstream error: {} - {}", statusCode, errBody);
            writeError(ctx, BAD_GATEWAY, "api_error", "Upstream API returned " + statusCode);
            return;
        }

        // Write SSE headers and then stream
        HttpResponse response = new DefaultHttpResponse(HTTP_1_1, OK);
        response.headers()
                .set(HttpHeaderNames.CONTENT_TYPE, "text/event-stream")
                .set(HttpHeaderNames.CACHE_CONTROL, "no-cache")
                .set(HttpHeaderNames.CONNECTION, "keep-alive")
                .set("x-request-id", "msg_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12));
        ctx.write(response);

        sseConversionService.convertStream(conn.getInputStream(), anthropicModel, event -> {
            ctx.writeAndFlush(Unpooled.copiedBuffer(event, CharsetUtil.UTF_8));
        });

        ctx.writeAndFlush(LastHttpContent.EMPTY_LAST_CONTENT);

        long elapsed = (System.currentTimeMillis() - start) / 1000;
        log.info("Stream request processed in {}s", elapsed);
    }

    // ── helpers ──

    private HttpURLConnection openConnection(String url) throws Exception {
        URL u = new URL(url);
        HttpURLConnection conn = (HttpURLConnection) u.openConnection();
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setConnectTimeout(30000);
        conn.setReadTimeout(300000);
        return conn;
    }

    private void writeJson(ChannelHandlerContext ctx, HttpResponseStatus status, Object data) {
        writeJson(ctx, status, data, Collections.emptyMap());
    }

    private void writeJson(ChannelHandlerContext ctx, HttpResponseStatus status, Object data, Map<String, String> extraHeaders) {
        try {
            byte[] bytes = mapper.writeValueAsBytes(data);
            FullHttpResponse resp = new DefaultFullHttpResponse(HTTP_1_1, status, Unpooled.wrappedBuffer(bytes));
            resp.headers()
                    .set(HttpHeaderNames.CONTENT_TYPE, "application/json; charset=utf-8")
                    .set(HttpHeaderNames.CACHE_CONTROL, "no-cache")
                    .set(HttpHeaderNames.CONTENT_LENGTH, bytes.length);
            for (Map.Entry<String, String> e : extraHeaders.entrySet()) {
                resp.headers().set(e.getKey(), e.getValue());
            }
            ctx.writeAndFlush(resp);
        } catch (Exception e) {
            log.error("Failed to write JSON response", e);
        }
    }

    private void writeError(ChannelHandlerContext ctx, HttpResponseStatus status, String errorType, String message) {
        ErrorResponse err = new ErrorResponse("error", errorType, message);
        try {
            byte[] bytes = mapper.writeValueAsBytes(err);
            FullHttpResponse resp = new DefaultFullHttpResponse(HTTP_1_1, status, Unpooled.wrappedBuffer(bytes));
            resp.headers()
                    .set(HttpHeaderNames.CONTENT_TYPE, "application/json; charset=utf-8")
                    .set(HttpHeaderNames.CACHE_CONTROL, "no-cache")
                    .set(HttpHeaderNames.CONTENT_LENGTH, bytes.length);
            ctx.writeAndFlush(resp);
        } catch (Exception e) {
            log.error("Failed to write error response", e);
        }
    }

    private void writeNoContent(ChannelHandlerContext ctx) {
        FullHttpResponse resp = new DefaultFullHttpResponse(HTTP_1_1, NO_CONTENT);
        ctx.writeAndFlush(resp);
    }

    private static String readStream(InputStream in) throws IOException {
        if (in == null) return "(no body)";
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        byte[] tmp = new byte[4096];
        int n;
        while ((n = in.read(tmp)) != -1) {
            buf.write(tmp, 0, n);
        }
        return buf.toString("UTF-8");
    }

    private static String stripTrailingSlash(String s) {
        return s.endsWith("/") ? s.substring(0, s.length() - 1) : s;
    }
}