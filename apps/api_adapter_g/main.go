// api_adapter_go — An OpenAI-to-Anthropic protocol adapter written in Go.
//
// It accepts Anthropic Messages API requests and forwards them to an
// OpenAI-compatible upstream LLM API, converting both request and response
// formats so that Anthropic clients (e.g. Claude Code) can use OpenAI models.
//
// Usage:
//
//	go run . [port]
//
// Port defaults to 16001 if not specified.
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

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds | log.Lshortfile)
	log.Println("[INFO] Starting api_adapter_go...")

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("[FATAL] Failed to load configuration: %v", err)
	}

	llmAPIURI := cfg.API.LLMAPIURI
	llmAPIKey := cfg.API.LLMAPIKey
	modelName := cfg.API.LLMModelName

	log.Printf("[INFO] Upstream URI: %s", llmAPIURI)
	log.Printf("[INFO] Model: %s", modelName)

	// Determine port
	port := 16001
	if len(os.Args) > 1 {
		if p, err := strconv.Atoi(os.Args[1]); err == nil {
			port = p
		}
	}

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

	log.Printf("[INFO] Listening on port %d, upstream=%s, model=%s", port, llmAPIURI, modelName)
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
