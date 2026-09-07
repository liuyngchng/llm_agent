package main

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
)

// abbrevHandler is a slog.Handler that formats log output with abbreviated
// source file paths (directory first-letters, no .go extension).
//
// Example output:
//
//	2026/09/07 10:11:43.609571 h/messages:138: [INFO] Stream request processed in 101.28s
//	2026/09/07 10:11:43.609571 i/w/test:10: [INFO] some message attr=value
type abbrevHandler struct {
	out   io.Writer
	mu    sync.Mutex
	root  string // module root directory, used to compute relative paths
	attrs []slog.Attr
	group string
}

// newLogger creates a new slog.Logger with the custom handler.
func newLogger(w io.Writer) *slog.Logger {
	// Determine the module root by finding the directory of main.go.
	// runtime.Caller(0) gives us this file, so we know the root.
	_, thisFile, _, _ := runtime.Caller(0)
	root := filepath.Dir(thisFile)

	return slog.New(&abbrevHandler{
		out:  w,
		root: root,
	})
}

func (h *abbrevHandler) Enabled(_ context.Context, level slog.Level) bool {
	return true // all levels enabled
}

func (h *abbrevHandler) Handle(_ context.Context, r slog.Record) error {
	h.mu.Lock()
	defer h.mu.Unlock()

	// Timestamp: same format as Ldate | Ltime | Lmicroseconds
	ts := r.Time.Format("2006/01/02 15:04:05.000000")

	// Source location
	src := h.sourceStr(r.PC)

	// Level as uppercase string in brackets
	levelStr := levelString(r.Level)

	// Build the message: keep original format with key=value pairs
	msg := r.Message

	// Collect attrs
	var attrBuf strings.Builder
	r.Attrs(func(a slog.Attr) bool {
		if a.Value.Kind() != slog.KindGroup {
			attrBuf.WriteString(" ")
			attrBuf.WriteString(a.Key)
			attrBuf.WriteString("=")
			attrBuf.WriteString(a.Value.String())
		}
		return true
	})

	// h.attrs prefix
	if len(h.attrs) > 0 {
		var prefix strings.Builder
		for _, a := range h.attrs {
			prefix.WriteString(" ")
			prefix.WriteString(a.Key)
			prefix.WriteString("=")
			prefix.WriteString(a.Value.String())
		}
		msg = prefix.String() + " " + msg
	}

	line := fmt.Sprintf("%s %s: %s %s%s\n", ts, src, levelStr, msg, attrBuf.String())
	_, err := h.out.Write([]byte(line))
	return err
}

func (h *abbrevHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	newH := *h
	newH.attrs = append(h.attrs, attrs...)
	return &newH
}

func (h *abbrevHandler) WithGroup(name string) slog.Handler {
	newH := *h
	newH.group = name
	return &newH
}

// sourceStr returns the abbreviated source path from a program counter.
// Example: /path/to/handler/messages.go → h/messages
func (h *abbrevHandler) sourceStr(pc uintptr) string {
	if pc == 0 {
		return ""
	}
	fs := runtime.CallersFrames([]uintptr{pc})
	f, _ := fs.Next()
	if f.File == "" {
		return ""
	}
	rel, err := filepath.Rel(h.root, f.File)
	if err != nil {
		rel = f.File
	}
	return abbreviatePath(rel) + ":" + itoa(f.Line)
}

// abbreviatePath transforms a file path by:
//   - Stripping the .go extension
//   - Abbreviating each directory segment to its first character
//
// Examples:
//
//	"handler/messages.go"  → "h/messages"
//	"internal/web/test.go" → "i/w/test"
//	"messages.go"          → "messages"
func abbreviatePath(path string) string {
	path = strings.TrimSuffix(path, ".go")
	dir, file := filepath.Split(path)
	if dir == "" || dir == "." {
		return file
	}
	dir = filepath.Clean(dir)
	parts := strings.Split(dir, string(filepath.Separator))
	var abbr []string
	for _, p := range parts {
		if p == "" || p == "." {
			continue
		}
		abbr = append(abbr, string([]rune(p)[0]))
	}
	if len(abbr) == 0 {
		return file
	}
	return strings.Join(abbr, "/") + "/" + file
}

// levelString converts a slog level to a bracketed uppercase string.
func levelString(l slog.Level) string {
	switch {
	case l >= slog.LevelError:
		return "[ERROR]"
	case l >= slog.LevelWarn:
		return "[WARN]"
	case l >= slog.LevelInfo:
		return "[INFO]"
	default:
		return "[DEBUG]"
	}
}

// itoa is a fast int-to-string conversion for small numbers.
func itoa(n int) string {
	if n < 0 {
		return "-" + uitoa(uint(-n))
	}
	return uitoa(uint(n))
}

func uitoa(n uint) string {
	if n == 0 {
		return "0"
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte(n%10) + '0'
		n /= 10
	}
	return string(buf[i:])
}

// setDefaultLogger configures the global slog default logger to write to w.
func setDefaultLogger(w io.Writer) {
	slog.SetDefault(newLogger(w))
}

// fatal logs an error message and exits with code 1.
func fatal(format string, args ...interface{}) {
	slog.Error(fmt.Sprintf(format, args...))
	os.Exit(1)
}