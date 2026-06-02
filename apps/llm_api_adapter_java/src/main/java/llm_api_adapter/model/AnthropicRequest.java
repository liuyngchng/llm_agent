package llm_api_adapter.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class AnthropicRequest {
    private String model;
    private String system;
    private List<Map<String, Object>> messages;
    private Integer maxTokens;
    private Double temperature;
    private Boolean stream;
    private List<String> stopSequences;
    private Double topP;
    private Integer topK;
    private List<Map<String, Object>> tools;
    private Map<String, Object> toolChoice;
    private Map<String, Object> thinking;
    private Map<String, String> metadata;

    public String getModel() { return model; }
    public void setModel(String v) { this.model = v; }
    public String getSystem() { return system; }
    public void setSystem(String v) { this.system = v; }
    public List<Map<String, Object>> getMessages() { return messages; }
    public void setMessages(List<Map<String, Object>> v) { this.messages = v; }
    public Integer getMaxTokens() { return maxTokens; }
    public void setMaxTokens(Integer v) { this.maxTokens = v; }
    public Double getTemperature() { return temperature; }
    public void setTemperature(Double v) { this.temperature = v; }
    public Boolean getStream() { return stream; }
    public void setStream(Boolean v) { this.stream = v; }
    public List<String> getStopSequences() { return stopSequences; }
    public void setStopSequences(List<String> v) { this.stopSequences = v; }
    public Double getTopP() { return topP; }
    public void setTopP(Double v) { this.topP = v; }
    public Integer getTopK() { return topK; }
    public void setTopK(Integer v) { this.topK = v; }
    public List<Map<String, Object>> getTools() { return tools; }
    public void setTools(List<Map<String, Object>> v) { this.tools = v; }
    public Map<String, Object> getToolChoice() { return toolChoice; }
    public void setToolChoice(Map<String, Object> v) { this.toolChoice = v; }
    public Map<String, Object> getThinking() { return thinking; }
    public void setThinking(Map<String, Object> v) { this.thinking = v; }
    public Map<String, String> getMetadata() { return metadata; }
    public void setMetadata(Map<String, String> v) { this.metadata = v; }
}