// api_adapter_go — An OpenAI-to-Anthropic protocol adapter written in Go.
//
// It accepts Anthropic Messages API requests and forwards them to an
// OpenAI-compatible upstream LLM API, converting both request and response
// formats so that Anthropic clients (e.g. Claude Code) can use OpenAI models.
//
// Usage:
//
//	api_adapter_go [options]
//
// See printUsage for the full set of options.
package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"api_adapter_go/config"
	"api_adapter_go/handler"
)

const defaultPort = 16001

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds | log.Lshortfile)

	// Parse command-line arguments (supports --help, --port, and positional port).
	cliPort, showHelp, err := parseArgs(os.Args[1:])
	if showHelp {
		printUsage()
		os.Exit(0)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n\n", err)
		printUsage()
		os.Exit(2)
	}

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		fmt.Fprintf(os.Stderr, "[FATAL] Failed to load configuration: %v\n", err)
		os.Exit(1)
	}

	// Connectivity check: verify the upstream LLM API is reachable.
	// This runs BEFORE log file setup so the result is printed to the console.
	if err := checkUpstreamConnectivity(cfg.API.LLMAPIURI, cfg.API.LLMAPIKey, cfg.API.LLMModelName); err != nil {
		fmt.Fprintf(os.Stderr, "[FATAL] Upstream connectivity check failed: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("[OK] Upstream connectivity check passed.")

	// Set up log output to file so logs persist and are viewable on both Windows and Linux.
	logFile, err := setupLogFile(cfg.Sys.LogFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[FATAL] Failed to set up log file %s: %v\n", cfg.Sys.LogFile, err)
		os.Exit(1)
	}
	if logFile != nil {
		defer logFile.Close()
		log.SetOutput(logFile)
	}

	log.Println("[INFO] Starting api_adapter_go...")

	llmAPIURI := cfg.API.LLMAPIURI
	llmAPIKey := cfg.API.LLMAPIKey
	modelName := cfg.API.LLMModelName

	// Determine listen port: CLI flag takes precedence, then config file, then hardcoded default.
	port := cfg.Sys.Port
	if cliPort != 0 {
		port = cliPort
	}

	log.Printf("[INFO] Upstream URI: %s", llmAPIURI)
	log.Printf("[INFO] Model: %s", modelName)

	// Build handler dependencies
	msgHandler := handler.NewMessagesHandler(llmAPIURI, llmAPIKey, modelName)
	modelsHandler := &handler.ModelsHandler{ModelName: modelName}

	// Set up routes using Go 1.22+ enhanced ServeMux patterns
	mux := http.NewServeMux()

	// /v1/messages
	mux.Handle("POST /v1/messages", msgHandler)

	// /v1/messages/count_tokens
	mux.HandleFunc("POST /v1/messages/count_tokens", modelsHandler.CountTokens)

	// /v1/models
	mux.HandleFunc("GET /v1/models", modelsHandler.ListModels)

	// /v1/models/{model_id}
	mux.HandleFunc("GET /v1/models/{model_id}", modelsHandler.GetModel)

	// /health
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		handler.Health(w, r, modelName, llmAPIURI)
	})

	// /
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		// Only match exact "/", not sub-paths
		if r.URL.Path != "/" {
			handler.WriteError(w, http.StatusNotFound, "invalid_request_error", "not found")
			return
		}
		handler.Welcome(w, r, modelName, llmAPIURI)
	})

	// Apply middleware stack: CORS → Auth → Logging
	var app http.Handler = mux
	// app = handler.AuthMiddleware(llmAPIKey)(app)
	app = handler.CORSMiddleware(app)

	// Wrap with recovery
	app = recoveryMiddleware(app)

	server := &http.Server{
		Addr:         fmt.Sprintf(":%d", port),
		Handler:      app,
		ReadTimeout:  60 * time.Second,
		WriteTimeout: 600 * time.Second, // Long timeout for streaming
		IdleTimeout:  120 * time.Second,
	}

	// Graceful shutdown
	go func() {
		sigCh := make(chan os.Signal, 1)
		signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
		sig := <-sigCh
		log.Printf("[INFO] Received signal %v, shutting down...", sig)

		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			log.Printf("[ERROR] Server shutdown error: %v", err)
		}
	}()

	// Detect local IPs for display
	localIPs := getLocalIPs()

	msg := fmt.Sprintf("[INFO] Service started on port %d. your ANTHROPIC_BASE_URL=\n", port)
	for _, ip := range localIPs {
		msg += fmt.Sprintf("          http://%s:%d\n", ip, port)
	}
	// Print the listening address to the console only; everything else goes to the log file.
	fmt.Print(msg)

	curlMsg := fmt.Sprintf("[INFO] You can test the endpoint with the following curl command:\n"+
		"    curl -X POST \"http://127.0.0.1:%d/v1/messages\" \\\n"+
		"      -H \"x-api-key: sk-***\" \\\n"+
		"      -H \"Content-Type: application/json\" \\\n"+
		"      -d '{\"model\":\"%s\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"max_tokens\":50}'\n",
		port, modelName)
	log.Print(curlMsg)
	log.Printf("[INFO] Listening on :%d, upstream=%s, model=%s", port, llmAPIURI, modelName)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("[FATAL] Server error: %v", err)
	}

	log.Println("[INFO] Server stopped")
}

// truncateStr truncates a string to maxLen characters for display.
func truncateStr(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen] + "..."
	}
	return s
}

// getLocalIPs returns all non-loopback IPv4 addresses of the local machine.
func getLocalIPs() []string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return []string{"127.0.0.1"}
	}

	var ips []string
	var loopback []string

	for _, iface := range interfaces {
		// Skip down interfaces
		if iface.Flags&net.FlagUp == 0 {
			continue
		}

		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}

		for _, addr := range addrs {
			ipNet, ok := addr.(*net.IPNet)
			if !ok {
				continue
			}
			ip := ipNet.IP.To4()
			if ip == nil {
				continue // skip IPv6
			}
			if ip.IsLoopback() {
				loopback = append(loopback, ip.String())
			} else {
				ips = append(ips, ip.String())
			}
		}
	}

	if len(ips) > 0 {
		return ips
	}
	if len(loopback) > 0 {
		return loopback
	}
	return []string{"127.0.0.1"}
}

// recoveryMiddleware catches panics in handlers and returns a 500 error.
func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Printf("[ERROR] Panic recovered: %v", rec)
				handler.WriteError(w, http.StatusInternalServerError, "internal_error", fmt.Sprintf("internal server error: %v", rec))
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// printUsage prints the help message to stdout.
func printUsage() {
	fmt.Print(`api_adapter_go — OpenAI-to-Anthropic API protocol adapter

Usage:
  api_adapter_go [options]
  api_adapter_go [port]          (backward-compatible shorthand)

Options:
  -p, --port <port>  Listen on the given port (default: ` + strconv.Itoa(defaultPort) + `).
                     Can also be set via sys.port in cfg.yml.
                     The port can also be passed as a positional argument
                     (e.g. "api_adapter_go 8080").
                     Priority: CLI flag > cfg.yml > built-in default.

  -h, --help         Show this help message and exit.

Environment:
  ADAPTER_CONFIG     Path to the YAML configuration file (default: cfg.yml).

Examples:
  # Run on the default port (16001)
  api_adapter_go

  # Run on a custom port
  api_adapter_go --port 8080
  api_adapter_go -p 8080
  api_adapter_go 8080

  # Use a custom config file
  ADAPTER_CONFIG=/path/to/cfg.yml api_adapter_go

  # Show help
  api_adapter_go --help
`)
}

// setupLogFile creates the log directory (if needed) and opens the log file
// for writing (overwriting existing content). It returns nil when the log file
// path is empty (meaning the caller should keep logging to stderr/stdout).
func setupLogFile(logPath string) (*os.File, error) {
	if logPath == "" {
		return nil, nil
	}

	if err := config.EnsureLogDir(logPath); err != nil {
		return nil, fmt.Errorf("create log directory: %w", err)
	}

	f, err := os.OpenFile(logPath, os.O_TRUNC|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return nil, fmt.Errorf("open log file: %w", err)
	}

	return f, nil
}

// parseArgs parses the command-line arguments and returns the port, whether
// help was requested, and any error encountered (e.g. invalid port value).
func parseArgs(args []string) (port int, showHelp bool, err error) {
	argsUsed := false

	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
			// -h or --help anywhere prints help and exits.
			return 0, true, nil
		case "-p", "--port":
			if i+1 >= len(args) {
				return 0, false, fmt.Errorf("missing value for %s", arg)
			}
			i++
			p, perr := strconv.Atoi(args[i])
			if perr != nil || p < 1 || p > 65535 {
				return 0, false, fmt.Errorf("invalid port: %q (must be 1–65535)", args[i])
			}
			port = p
			argsUsed = true
		default:
			// Treat any unrecognised non-flag argument as a positional port.
			if argsUsed {
				return 0, false, fmt.Errorf("unexpected argument: %s", arg)
			}
			p, perr := strconv.Atoi(arg)
			if perr != nil || p < 1 || p > 65535 {
				return 0, false, fmt.Errorf("invalid port: %q (must be 1–65535)", arg)
			}
			port = p
			argsUsed = true
		}
	}
	return port, false, nil
}

// checkUpstreamConnectivity sends a lightweight request to the upstream LLM API
// to verify the URI, API key, and model name are correct. All output goes to
// stdout/stderr so it is visible in the console before the log file is set up.
func checkUpstreamConnectivity(uri, apiKey, modelName string) error {
	fmt.Printf("[INFO] Checking upstream connectivity to %s ...\n", uri)

	// Build a minimal chat completion request to test connectivity.
	reqBody := map[string]interface{}{
		"model": modelName,
		"messages": []map[string]string{
			{"role": "user", "content": "hi"},
		},
		"max_tokens": 1,
	}
	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("marshal test request: %w", err)
	}

	baseURI := strings.TrimRight(uri, "/")
	upstreamURL := fmt.Sprintf("%s/chat/completions", baseURI)

	req, err := http.NewRequest(http.MethodPost, upstreamURL, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("create test request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+apiKey)

	client := &http.Client{
		Timeout: 15 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				InsecureSkipVerify: true,
			},
			Proxy: nil,
		},
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("cannot reach upstream API %q: %w", uri, err)
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	if resp.StatusCode == http.StatusOK {
		fmt.Printf("[INFO] Upstream API responded with 200 OK.\n")
		return nil
	}

	switch resp.StatusCode {
	case http.StatusUnauthorized:
		return fmt.Errorf("upstream API returned 401 Unauthorized — check your llm_api_key. Response: %s",
			truncateStr(string(respBody), 200))
	case http.StatusForbidden:
		return fmt.Errorf("upstream API returned 403 Forbidden — check your llm_api_key permissions. Response: %s",
			truncateStr(string(respBody), 200))
	case http.StatusNotFound:
		return fmt.Errorf("upstream API returned 404 Not Found — check your llm_api_uri (%q). Response: %s",
			uri, truncateStr(string(respBody), 200))
	default:
		return fmt.Errorf("upstream API returned unexpected status %d. Response: %s",
			resp.StatusCode, truncateStr(string(respBody), 200))
	}
}
