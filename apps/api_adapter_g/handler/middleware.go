// Package handler provides HTTP handlers and middleware for the API adapter.
package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"
)

// ---------------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------------

// ExtractAPIKey extracts the API key from request headers.
// It checks x-api-key first, then Authorization: Bearer.
func ExtractAPIKey(r *http.Request) string {
	if key := r.Header.Get("x-api-key"); key != "" {
		return key
	}
	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "Bearer ") {
		return auth[7:]
	}
	return ""
}

// AuthMiddleware returns a middleware that validates the API key.
func AuthMiddleware(apiKey string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip auth if no API key is configured
			if apiKey == "" {
				next.ServeHTTP(w, r)
				return
			}

			clientKey := ExtractAPIKey(r)
			if clientKey != apiKey {
				log.Printf("[WARN] Invalid API key attempt. Expected prefix: %s..., Got prefix: %s...",
					truncate(apiKey, 20), truncate(clientKey, 20))
				WriteJSON(w, http.StatusUnauthorized, map[string]interface{}{
					"type": "error",
					"error": map[string]interface{}{
						"type":    "authentication_error",
						"message": "invalid api key",
					},
				})
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

func truncate(s string, maxLen int) string {
	if len(s) > maxLen {
		return s[:maxLen]
	}
	if s == "" {
		return "None"
	}
	return s
}

// ---------------------------------------------------------------------------
// CORS
// ---------------------------------------------------------------------------

// CORSMiddleware adds permissive CORS headers to all responses.
func CORSMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization, x-api-key, anthropic-version")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// ---------------------------------------------------------------------------
// JSON response helpers
// ---------------------------------------------------------------------------

// WriteJSON writes a JSON response with proper headers.
func WriteJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.WriteHeader(status)

	if err := json.NewEncoder(w).Encode(data); err != nil {
		log.Printf("[ERROR] Failed to write JSON response: %v", err)
	}
}

// WriteError writes a standard Anthropic-format error response.
func WriteError(w http.ResponseWriter, status int, errorType, message string) {
	WriteJSON(w, status, map[string]interface{}{
		"type": "error",
		"error": map[string]interface{}{
			"type":    errorType,
			"message": message,
		},
	})
}
