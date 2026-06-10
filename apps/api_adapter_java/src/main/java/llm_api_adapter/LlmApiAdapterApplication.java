package llm_api_adapter;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;

@SpringBootApplication
public class LlmApiAdapterApplication {

    private static final Logger log = LoggerFactory.getLogger(LlmApiAdapterApplication.class);

    public static void main(String[] args) {
        // let ConfigLoader set system properties before Spring starts
        String cfgPath = "config.yml";
        if (!new java.io.File(cfgPath).exists()) {
            cfgPath = "cfg.yml";
        }
        llm_api_adapter.config.ConfigLoader.loadToSystem(cfgPath);
        SpringApplication.run(LlmApiAdapterApplication.class, args);
    }

    @EventListener(ApplicationReadyEvent.class)
    public void onReady() {
        log.info("llm_api_adapter started, listening_port={}, upstream={}, model={}",
                System.getProperty("server.port", "16001"),
                System.getProperty("app.llm-api-uri", "unknown"),
                System.getProperty("app.llm-model-name", "unknown"));
    }
}