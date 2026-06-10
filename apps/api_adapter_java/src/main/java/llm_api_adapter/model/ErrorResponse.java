package llm_api_adapter.model;

public class ErrorResponse {
    private String type;
    private ErrorDetail error;

    public ErrorResponse() {}
    public ErrorResponse(String type, String errorType, String message) {
        this.type = type;
        this.error = new ErrorDetail(errorType, message);
    }

    public String getType() { return type; }
    public void setType(String v) { this.type = v; }
    public ErrorDetail getError() { return error; }
    public void setError(ErrorDetail v) { this.error = v; }

    public static class ErrorDetail {
        private String type;
        private String message;

        public ErrorDetail() {}
        public ErrorDetail(String type, String message) {
            this.type = type;
            this.message = message;
        }

        public String getType() { return type; }
        public void setType(String v) { this.type = v; }
        public String getMessage() { return message; }
        public void setMessage(String v) { this.message = v; }
    }
}