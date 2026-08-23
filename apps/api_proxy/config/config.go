// Package config loads and provides YAML configuration for the API proxy.
package config

import (
	"fmt"
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Config holds the application configuration.
type Config struct {
	Sys SysConfig `yaml:"sys"`
	API APIConfig `yaml:"api"`
}

// DefaultProxyPort is the fallback listen port when none is configured.
const DefaultProxyPort = 17001

// DefaultProxyLogFile is the fallback log file path when none is configured.
const DefaultProxyLogFile = "logs/api_proxy.log"

// SysConfig holds system-level configuration.
// Uses proxy_port / proxy_log_file so it can coexist with api_adapter_g
// in a shared cfg.yml without field name collisions.
type SysConfig struct {
	Name      string `yaml:"name"`
	ProxyPort int    `yaml:"proxy_port"`
	LogFile   string `yaml:"proxy_log_file"`
}

// APIConfig holds the upstream LLM API configuration.
type APIConfig struct {
	LLMAPIURI    string `yaml:"llm_api_uri"`
	LLMAPIKey    string `yaml:"llm_api_key"`
	LLMModelName string `yaml:"llm_model_name"`
}

// EnsureLogDir creates the directory for the log file if it doesn't exist.
func EnsureLogDir(logPath string) error {
	dir := filepath.Dir(logPath)
	if dir == "." || dir == "" {
		return nil
	}
	return os.MkdirAll(dir, 0755)
}

// Load reads and parses the YAML configuration file.
// It looks for cfg.yml in the current directory or at the path
// specified by the PROXY_CONFIG environment variable.
func Load() (*Config, error) {
	path := "cfg.yml"
	if envPath := os.Getenv("PROXY_CONFIG"); envPath != "" {
		path = envPath
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf(
				"\n\n  Configuration file not found: %s\n\n"+
					"  To get started:\n"+
					"    1. Copy the template:  cp cfg.yml.template cfg.yml\n"+
					"    2. Edit cfg.yml with your upstream API credentials\n\n"+
					"  Or set a custom config path:\n"+
					"    PROXY_CONFIG=/path/to/cfg.yml ./api_proxy\n", path)
		}
		return nil, fmt.Errorf("read config file %s: %w", path, err)
	}

	cfg := &Config{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parse config file %s: %w", path, err)
	}

	// Validate required fields
	if cfg.API.LLMAPIURI == "" {
		return nil, fmt.Errorf("missing required config: api.llm_api_uri (upstream API base URL)")
	}
	if cfg.API.LLMAPIKey == "" {
		return nil, fmt.Errorf("missing required config: api.llm_api_key (upstream API key)")
	}

	// Apply defaults
	if cfg.Sys.ProxyPort == 0 {
		cfg.Sys.ProxyPort = DefaultProxyPort
	}
	if cfg.Sys.ProxyPort < 1 || cfg.Sys.ProxyPort > 65535 {
		return nil, fmt.Errorf("invalid config: sys.proxy_port must be 1–65535, got %d", cfg.Sys.ProxyPort)
	}
	if cfg.Sys.LogFile == "" {
		cfg.Sys.LogFile = DefaultProxyLogFile
	}

	// Trim trailing slash from URI
	if len(cfg.API.LLMAPIURI) > 0 && cfg.API.LLMAPIURI[len(cfg.API.LLMAPIURI)-1] == '/' {
		cfg.API.LLMAPIURI = cfg.API.LLMAPIURI[:len(cfg.API.LLMAPIURI)-1]
	}

	return cfg, nil
}