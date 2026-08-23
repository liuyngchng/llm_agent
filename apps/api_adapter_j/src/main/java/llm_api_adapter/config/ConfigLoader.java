package llm_api_adapter.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.FileInputStream;
import java.io.InputStream;
import java.util.Map;

/**
 * Loads config.yml/cfg.yml into a {@link Config} object. Environment variables
 * (SERVER_PORT, LLM_API_URI, LLM_API_KEY, LLM_MODEL_NAME) override the file.
 */
public class ConfigLoader {
    private static final Logger log = LoggerFactory.getLogger(ConfigLoader.class);

    @SuppressWarnings("unchecked")
    public static Config load(String path) {
        Config cfg = new Config();
        try (InputStream in = new FileInputStream(path)) {
            Yaml yaml = new Yaml();
            Map<String, Object> root = yaml.load(in);
            Map<String, Object> api = (Map<String, Object>) root.get("api");
            if (api != null) {
                cfg.setLlmApiUri(str(api.get("llm_api_uri"), cfg.getLlmApiUri()));
                cfg.setLlmApiKey(str(api.get("llm_api_key"), ""));
                cfg.setLlmModelName(str(api.get("llm_model_name"), cfg.getLlmModelName()));
            }
            Map<String, Object> sys = (Map<String, Object>) root.get("sys");
            if (sys != null) {
                if (sys.get("name") != null) cfg.setName(sys.get("name").toString());
                if (sys.get("port") != null) cfg.setPort(toInt(sys.get("port"), cfg.getPort()));
                if (sys.get("log_file") != null) cfg.setLogFile(sys.get("log_file").toString());
            }
            log.info("Loaded config from {}: uri={}, model={}", path, cfg.getLlmApiUri(), cfg.getLlmModelName());
        } catch (Exception e) {
            log.warn("Failed to load config from {}: {}. Using env/fallback defaults.", path, e.getMessage());
            cfg.setLlmApiUri(env("LLM_API_URI", cfg.getLlmApiUri()));
            cfg.setLlmApiKey(env("LLM_API_KEY", ""));
            cfg.setLlmModelName(env("LLM_MODEL_NAME", cfg.getLlmModelName()));
        }

        // Environment always overrides
        if (System.getenv("SERVER_PORT") != null) cfg.setPort(toInt(System.getenv("SERVER_PORT"), cfg.getPort()));
        if (System.getenv("LLM_API_URI") != null) cfg.setLlmApiUri(System.getenv("LLM_API_URI"));
        if (System.getenv("LLM_API_KEY") != null) cfg.setLlmApiKey(System.getenv("LLM_API_KEY"));
        if (System.getenv("LLM_MODEL_NAME") != null) cfg.setLlmModelName(System.getenv("LLM_MODEL_NAME"));

        return cfg;
    }

    private static String str(Object v, String def) {
        return v != null ? v.toString() : def;
    }

    private static String env(String key, String def) {
        String v = System.getenv(key);
        return v != null ? v : def;
    }

    private static int toInt(Object v, int def) {
        try {
            return v instanceof Number ? ((Number) v).intValue() : Integer.parseInt(v.toString().trim());
        } catch (Exception e) {
            return def;
        }
    }
}
