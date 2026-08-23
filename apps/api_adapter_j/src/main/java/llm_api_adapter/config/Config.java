package llm_api_adapter.config;

/**
 * Plain config holder loaded from config.yml/cfg.yml (or environment fallbacks).
 */
public class Config {

    private String name = "LLM API Adapter";
    private int port = 16001;
    private String logFile = "logs/api_adapter.log";

    private String llmApiUri = "http://localhost:8000/v1";
    private String llmApiKey = "";
    private String llmModelName = "deepseek-chat";

    public String getName() { return name; }
    public void setName(String v) { this.name = v; }
    public int getPort() { return port; }
    public void setPort(int v) { this.port = v; }
    public String getLogFile() { return logFile; }
    public void setLogFile(String v) { this.logFile = v; }
    public String getLlmApiUri() { return llmApiUri; }
    public void setLlmApiUri(String v) { this.llmApiUri = v; }
    public String getLlmApiKey() { return llmApiKey; }
    public void setLlmApiKey(String v) { this.llmApiKey = v; }
    public String getLlmModelName() { return llmModelName; }
    public void setLlmModelName(String v) { this.llmModelName = v; }
}
