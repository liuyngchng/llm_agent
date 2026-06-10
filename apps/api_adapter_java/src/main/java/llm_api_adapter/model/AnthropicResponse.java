package llm_api_adapter.model;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonInclude(JsonInclude.Include.NON_NULL)
public class AnthropicResponse {
    private String id;
    private String type;
    private String role;
    private String model;
    private List<ContentBlock> content;
    private String stopReason;
    private String stopSequence;
    private Usage usage;

    public String getId() { return id; }
    public void setId(String v) { this.id = v; }
    public String getType() { return type; }
    public void setType(String v) { this.type = v; }
    public String getRole() { return role; }
    public void setRole(String v) { this.role = v; }
    public String getModel() { return model; }
    public void setModel(String v) { this.model = v; }
    public List<ContentBlock> getContent() { return content; }
    public void setContent(List<ContentBlock> v) { this.content = v; }
    @JsonProperty("stop_reason")
    public String getStopReason() { return stopReason; }
    @JsonProperty("stop_reason")
    public void setStopReason(String v) { this.stopReason = v; }
    @JsonProperty("stop_sequence")
    public String getStopSequence() { return stopSequence; }
    @JsonProperty("stop_sequence")
    public void setStopSequence(String v) { this.stopSequence = v; }
    public Usage getUsage() { return usage; }
    public void setUsage(Usage v) { this.usage = v; }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class ContentBlock {
        private String type;
        private String text;
        private String id;
        private String name;
        private Object input;
        private String thinking;
        private String signature;

        public String getType() { return type; }
        public void setType(String v) { this.type = v; }
        public String getText() { return text; }
        public void setText(String v) { this.text = v; }
        public String getId() { return id; }
        public void setId(String v) { this.id = v; }
        public String getName() { return name; }
        public void setName(String v) { this.name = v; }
        public Object getInput() { return input; }
        public void setInput(Object v) { this.input = v; }
        public String getThinking() { return thinking; }
        public void setThinking(String v) { this.thinking = v; }
        public String getSignature() { return signature; }
        public void setSignature(String v) { this.signature = v; }
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class Usage {
        private int inputTokens;
        private int outputTokens;

        @JsonProperty("input_tokens")
        public int getInputTokens() { return inputTokens; }
        @JsonProperty("input_tokens")
        public void setInputTokens(int v) { this.inputTokens = v; }
        @JsonProperty("output_tokens")
        public int getOutputTokens() { return outputTokens; }
        @JsonProperty("output_tokens")
        public void setOutputTokens(int v) { this.outputTokens = v; }
    }
}