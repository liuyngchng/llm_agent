package llm_api_adapter.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class AppConfig {

    @Value("${app.llm-api-uri}")
    private String llmApiUri;

    @Value("${app.llm-api-key:}")
    private String llmApiKey;

    @Value("${app.llm-model-name}")
    private String llmModelName;

    public String getLlmApiUri() { return llmApiUri; }
    public String getLlmApiKey() { return llmApiKey; }
    public String getLlmModelName() { return llmModelName; }
}