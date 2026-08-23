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
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"api_adapter_go/config"
	"api_adapter_go/handler"
)

const defaultPort = 16001

func main() {
	log.SetOutput(os.Stdout)
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

	log.Println("[INFO] Starting api_adapter_go...")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("[FATAL] Failed to load configuration: %v", err)
	}

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
	app = handler.AuthMiddleware(llmAPIKey)(app)
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

	log.Printf("[INFO] Service started. Test it with:\n\n"+
		"  curl -X POST \"http://127.0.0.1:%d/v1/messages\" \\\n"+
		"    -H \"x-api-key: sk-***\" \\\n"+
		"    -H \"Content-Type: application/json\" \\\n"+
		"    -d '{\"model\":\"%s\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"max_tokens\":50}'\n",
		port, modelName)
	log.Printf("[INFO] Listening on :%d, upstream=%s, model=%s", port, llmAPIURI, modelName)
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("[FATAL] Server error: %v", err)
	}

	log.Println("[INFO] Server stopped")
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
