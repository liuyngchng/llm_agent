// api_proxy — A transparent OpenAI API proxy written in Go.
//
// It listens on a configurable address and forwards all incoming HTTP requests
// to an upstream OpenAI-compatible LLM API, injecting the configured API key.
// No authentication is required on the incoming side.
//
// System proxy environment variables (HTTP_PROXY, HTTPS_PROXY, etc.) are
// explicitly ignored when forwarding to the upstream API.
//
// Usage:
//
//	api_proxy [options]
//
// See printUsage for the full set of options.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"api_proxy/config"
)

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds | log.Lshortfile)

	// Parse command-line arguments
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

	// Set up log file
	logFile, err := setupLogFile(cfg.Sys.LogFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "[FATAL] Failed to set up log file %s: %v\n", cfg.Sys.LogFile, err)
		os.Exit(1)
	}
	if logFile != nil {
		defer logFile.Close()
		log.SetOutput(logFile)
	}

	log.Println("[INFO] Starting api_proxy...")

	upstreamURI := cfg.API.LLMAPIURI
	apiKey := cfg.API.LLMAPIKey
	modelName := cfg.API.LLMModelName

	// Determine listen port: CLI flag > config file > default
	port := cfg.Sys.ProxyPort
	if cliPort != 0 {
		port = cliPort
	}
	listenAddr := fmt.Sprintf(":%d", port)

	log.Printf("[INFO] Upstream URI: %s", upstreamURI)
	log.Printf("[INFO] Model: %s", modelName)

	// Parse upstream URL
	upstreamURL, err := url.Parse(upstreamURI)
	if err != nil {
		log.Fatalf("[FATAL] Invalid upstream URI %q: %v", upstreamURI, err)
	}

	// Build reverse proxy
	proxy := &httputil.ReverseProxy{
		Rewrite: func(pr *httputil.ProxyRequest) {
			// Rewrite the target URL to point to the upstream, keeping the
			// incoming path but ensuring the upstream base path is present
			// exactly once.
			pr.Out.URL.Scheme = upstreamURL.Scheme
			pr.Out.URL.Host = upstreamURL.Host
			pr.Out.URL.Path = rewritePath(upstreamURL.Path, pr.In.URL.Path)
			pr.Out.URL.RawQuery = pr.In.URL.RawQuery

			// Inject the upstream API key
			pr.Out.Header.Set("Authorization", "Bearer "+apiKey)

			// Drop any client-supplied auth header so it can't interfere.
			pr.Out.Header.Del("x-api-key")

			// Set X-Forwarded-For
			clientIP, _, _ := net.SplitHostPort(pr.In.RemoteAddr)
			if existing := pr.In.Header.Get("X-Forwarded-For"); existing != "" {
				pr.Out.Header.Set("X-Forwarded-For", existing+", "+clientIP)
			} else {
				pr.Out.Header.Set("X-Forwarded-For", clientIP)
			}
		},
		Transport: &http.Transport{
			// Explicitly set Proxy to nil to ignore system proxy environment
			// variables (HTTP_PROXY, HTTPS_PROXY, NO_PROXY, etc.)
			Proxy: nil,

			DialContext: (&net.Dialer{
				Timeout:   30 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
			MaxIdleConns:          100,
			IdleConnTimeout:       90 * time.Second,
			TLSHandshakeTimeout:   10 * time.Second,
			ExpectContinueTimeout: 1 * time.Second,
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			log.Printf("[ERROR] Proxy error for %s %s: %v", r.Method, r.URL.Path, err)
			http.Error(w, fmt.Sprintf(`{"error":{"message":"proxy error: %s","type":"proxy_error"}}`, err.Error()),
				http.StatusBadGateway)
		},
	}

	// Build the handler chain
	mux := http.NewServeMux()

	// Health check endpoint
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"ok","upstream":"%s","model":"%s","listen":"%s"}`,
			upstreamURI, modelName, listenAddr)
	})

	// Root endpoint
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"service":"api_proxy","upstream":"%s","model":"%s","listen":"%s"}`, upstreamURI, modelName, listenAddr)
	})

	// All other requests go through the proxy with request/response logging
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		startTime := time.Now()

		// Read and log the request body (truncated), then restore it for
		// the reverse proxy to forward.
		bodyBytes, err := io.ReadAll(r.Body)
		if err != nil {
			log.Printf("[ERROR] Failed to read request body: %v", err)
			http.Error(w, `{"error":{"message":"failed to read request body","type":"proxy_error"}}`, http.StatusBadRequest)
			return
		}
		r.Body.Close()
		r.Body = io.NopCloser(bytes.NewReader(bodyBytes))

		log.Printf("[DEBUG] Request body: %s", truncateStr(string(bodyBytes), 500))

		// Parse model and stream info from the request body for logging
		var bodyData map[string]interface{}
		reqModel := "-"
		reqStream := false
		if json.Unmarshal(bodyBytes, &bodyData) == nil {
			if m, ok := bodyData["model"].(string); ok {
				reqModel = m
			}
			if s, ok := bodyData["stream"].(bool); ok {
				reqStream = s
			}
		}

		log.Printf("[INFO] forward to %s, model=%s, stream=%v", rewritePath(upstreamURL.Path, r.URL.Path), reqModel, reqStream)

		proxy.ServeHTTP(w, r)

		elapsed := time.Since(startTime)
		log.Printf("[INFO] %s request processed in %.2fs", r.URL.Path, elapsed.Seconds())
	})

	// Apply middleware
	var app http.Handler = mux
	app = corsMiddleware(app)
	app = recoveryMiddleware(app)

	server := &http.Server{
		Addr:         listenAddr,
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
	msg := fmt.Sprintf("[INFO] Service started on port %d. OpenAI base URL:\n", port)
	for _, ip := range localIPs {
		msg += fmt.Sprintf("          http://%s:%d\n", ip, port)
	}
	// Print the listening address to the console only; everything else goes to the log file.
	fmt.Print(msg)

	curlMsg := fmt.Sprintf("[INFO] You can test the endpoint with the following curl command:\n"+
		"    curl -X POST \"http://127.0.0.1:%d/v1/chat/completions\" \\\n"+
		"      -H \"Content-Type: application/json\" \\\n"+
		"      -d '{\"model\":\"%s\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}],\"max_tokens\":50}'\n",
		port, modelName)
	log.Print(curlMsg)
	log.Printf("[INFO] Listening on :%d, upstream=%s", port, upstreamURI)
	log.Printf("[INFO] No auth required on incoming requests — upstream key injected automatically")
	log.Printf("[INFO] System proxy env vars (HTTP_PROXY, HTTPS_PROXY, etc.) are IGNORED for upstream connections")

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("[FATAL] Server error: %v", err)
	}

	log.Println("[INFO] Server stopped")
}

// corsMiddleware adds permissive CORS headers to all responses.
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-key")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// statusRecorder wraps http.ResponseWriter to track whether WriteHeader has
// been called, so the recovery middleware can avoid writing a second status.
type statusRecorder struct {
	http.ResponseWriter
	wroteHeader bool
	status      int
}

func (r *statusRecorder) WriteHeader(status int) {
	if r.wroteHeader {
		return
	}
	r.wroteHeader = true
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func (r *statusRecorder) Write(b []byte) (int, error) {
	if !r.wroteHeader {
		r.WriteHeader(http.StatusOK)
	}
	return r.ResponseWriter.Write(b)
}

// Unwrap returns the underlying ResponseWriter for http.ResponseController.
func (r *statusRecorder) Unwrap() http.ResponseWriter {
	return r.ResponseWriter
}

// recoveryMiddleware catches panics in handlers.  If the panic is caused by a
// client disconnect (net/http: abort Handler), it is logged at INFO level
// because this is normal for streaming responses.  Other panics are logged at
// ERROR level.  A 500 response is only written if headers have not yet been
// sent.
func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sr := &statusRecorder{ResponseWriter: w, status: http.StatusOK}
		defer func() {
			if rec := recover(); rec != nil {
				errMsg := fmt.Sprintf("%v", rec)
				if errMsg == "net/http: abort Handler" {
					log.Printf("[INFO] Client disconnected (abort Handler) for %s %s", r.Method, r.URL.Path)
				} else {
					log.Printf("[ERROR] Panic recovered: %v", rec)
				}
				if !sr.wroteHeader {
					http.Error(sr, fmt.Sprintf(`{"error":{"message":"internal server error","type":"internal_error"}}`),
						http.StatusInternalServerError)
				}
			}
		}()
		next.ServeHTTP(sr, r)
	})
}

// rewritePath ensures the incoming path is prefixed with the upstream base
// path exactly once.  If the incoming path already starts with the base path,
// it is returned as-is; otherwise the base path is prepended.
//
// Examples with base="/v1":
//
//	"/v1/chat/completions" → "/v1/chat/completions"
//	"/chat/completions"    → "/v1/chat/completions"
//	"/"                    → "/v1/"
func rewritePath(base, incoming string) string {
	if base == "" || base == "/" {
		return incoming
	}
	// Normalise: both have a leading slash, base has no trailing slash.
	if !strings.HasPrefix(base, "/") {
		base = "/" + base
	}
	base = strings.TrimSuffix(base, "/")
	if !strings.HasPrefix(incoming, "/") {
		incoming = "/" + incoming
	}
	if strings.HasPrefix(incoming, base+"/") || incoming == base {
		return incoming
	}
	return base + incoming
}

// truncateStr truncates a string to maxLen characters for logging.
func truncateStr(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen]
	}
	return s
}

// getLocalIPs returns all non-loopback IPv4 addresses of the local machine.
// If no non-loopback IP is found, it falls back to loopback addresses.
func getLocalIPs() []string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return []string{"127.0.0.1"}
	}

	var ips []string
	var loopback []string

	for _, iface := range interfaces {
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
				continue
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

// setupLogFile creates the log directory and opens the log file for writing
// (overwriting existing content).
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

// parseArgs parses command-line arguments.
func parseArgs(args []string) (port int, showHelp bool, err error) {
	argsUsed := false
	for i := 0; i < len(args); i++ {
		arg := args[i]
		switch arg {
		case "-h", "--help":
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
			// Treat unrecognised non-flag argument as a positional port
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

// printUsage prints the help message.
func printUsage() {
	fmt.Print(`api_proxy — OpenAI API transparent proxy

Usage:
  api_proxy [options]
  api_proxy [port]              (backward-compatible shorthand)

Options:
  -p, --port <port>  Listen on the given port (default: ` + strconv.Itoa(config.DefaultProxyPort) + `).
                     Can also be set via sys.proxy_port in cfg.yml.
                     Priority: CLI flag > cfg.yml > built-in default.

  -h, --help         Show this help message and exit.

Environment:
  PROXY_CONFIG       Path to the YAML configuration file (default: cfg.yml).

Examples:
  # Run on the default port (17001)
  api_proxy

  # Run on a custom port
  api_proxy --port 8080
  api_proxy -p 8080
  api_proxy 8080

  # Use a custom config file
  PROXY_CONFIG=/path/to/cfg.yml ./api_proxy

Shared cfg.yml with api_adapter_g:
  Both programs can share a cfg.yml. The api section is identical;
  sys section uses different field names (port vs proxy_port, log_file vs proxy_log_file).

  sys:
    name: LLM API Services
    port: 16001                    # api_adapter_g
    proxy_port: 17001              # api_proxy
    log_file: logs/api_adapter.log  # api_adapter_g
    proxy_log_file: logs/api_proxy.log  # api_proxy

  api:
    llm_api_uri: https://api.deepseek.com/v1
    llm_api_key: sk-xxx
    llm_model_name: deepseek-chat

Behavior:
  - All incoming requests are forwarded to the upstream LLM API as-is.
  - The upstream API key is injected from cfg.yml — no auth on incoming side.
  - System proxy environment variables (HTTP_PROXY, HTTPS_PROXY, etc.) are
    explicitly ignored for upstream connections.
`)
}

