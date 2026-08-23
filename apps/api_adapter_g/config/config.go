// Package config loads and provides YAML configuration for the API adapter.
package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// Config holds the application configuration.
type Config struct {
	Sys SysConfig `yaml:"sys"`
	API APIConfig `yaml:"api"`
}

// DefaultPort is the fallback listen port when none is configured.
const DefaultPort = 16001

// SysConfig holds system-level configuration.
type SysConfig struct {
	Name string `yaml:"name"`
	Port int    `yaml:"port"`
}

// APIConfig holds the upstream LLM API configuration.
type APIConfig struct {
	LLMAPIURI   string `yaml:"llm_api_uri"`
	LLMAPIKey   string `yaml:"llm_api_key"`
	LLMModelName string `yaml:"llm_model_name"`
}

// Load reads and parses the YAML configuration file.
// It looks for cfg.yml in the current directory or at the path
// specified by the ADAPTER_CONFIG environment variable.
func Load() (*Config, error) {
	path := "cfg.yml"
	if envPath := os.Getenv("ADAPTER_CONFIG"); envPath != "" {
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
					"    ADAPTER_CONFIG=/path/to/cfg.yml ./api_adapter_g\n", path)
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
	if cfg.API.LLMModelName == "" {
		return nil, fmt.Errorf("missing required config: api.llm_model_name (default model name)")
	}

	// Apply the default listen port when none is configured.
	if cfg.Sys.Port == 0 {
		cfg.Sys.Port = DefaultPort
	}
	if cfg.Sys.Port < 1 || cfg.Sys.Port > 65535 {
		return nil, fmt.Errorf("invalid config: sys.port must be 1–65535, got %d", cfg.Sys.Port)
	}

	// Trim trailing slash from URI
	if cfg.API.LLMAPIURI[len(cfg.API.LLMAPIURI)-1] == '/' {
		cfg.API.LLMAPIURI = cfg.API.LLMAPIURI[:len(cfg.API.LLMAPIURI)-1]
	}

	return cfg, nil
}
