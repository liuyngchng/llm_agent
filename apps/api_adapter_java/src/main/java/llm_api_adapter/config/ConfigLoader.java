package llm_api_adapter.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

import java.io.FileInputStream;
import java.io.InputStream;
import java.util.Map;

/**
 * Loads config.yml/cfg.yml and sets System properties so Spring @Value can read them.
 */
public class ConfigLoader {
    private static final Logger log = LoggerFactory.getLogger(ConfigLoader.class);

    @SuppressWarnings("unchecked")
    public static void loadToSystem(String path) {
        try (InputStream in = new FileInputStream(path)) {
            Yaml yaml = new Yaml();
            Map<String, Object> root = yaml.load(in);
            Map<String, Object> api = (Map<String, Object>) root.get("api");
            if (api != null) {
                setSysProp("app.llm-api-uri", api.get("llm_api_uri"), "http://localhost:8000/v1");
                setSysProp("app.llm-api-key", api.get("llm_api_key"), "");
                setSysProp("app.llm-model-name", api.get("llm_model_name"), "deepseek-chat");
            }
            // server port from sys section or env
            Map<String, Object> sys = (Map<String, Object>) root.get("sys");
            if (sys != null && sys.containsKey("port")) {
                setSysProp("server.port", sys.get("port"), "16001");
            }
            if (System.getenv("SERVER_PORT") != null) {
                System.setProperty("server.port", System.getenv("SERVER_PORT"));
            }
            log.info("Loaded config from {}: uri={}, model={}", path,
                    System.getProperty("app.llm-api-uri"),
                    System.getProperty("app.llm-model-name"));
        } catch (Exception e) {
            log.warn("Failed to load config from {}: {}. Using env/fallback defaults.", path, e.getMessage());
            // env fallback
            setSysPropFromEnv("app.llm-api-uri", "LLM_API_URI", "http://localhost:8000/v1");
            setSysPropFromEnv("app.llm-api-key", "LLM_API_KEY", "");
            setSysPropFromEnv("app.llm-model-name", "LLM_MODEL_NAME", "deepseek-chat");
        }
        // env always overrides
        if (System.getenv("LLM_API_URI") != null)
            System.setProperty("app.llm-api-uri", System.getenv("LLM_API_URI"));
        if (System.getenv("LLM_API_KEY") != null)
            System.setProperty("app.llm-api-key", System.getenv("LLM_API_KEY"));
        if (System.getenv("LLM_MODEL_NAME") != null)
            System.setProperty("app.llm-model-name", System.getenv("LLM_MODEL_NAME"));
    }

    private static void setSysProp(String key, Object val, String def) {
        System.setProperty(key, val != null ? val.toString() : def);
    }

    private static void setSysPropFromEnv(String key, String envName, String def) {
        String v = System.getenv(envName);
        System.setProperty(key, v != null ? v : def);
    }
}