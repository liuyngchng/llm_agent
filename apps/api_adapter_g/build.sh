#!/bin/bash
set -e

echo "=== Cleaning up previous build artifacts ==="
rm -f api_adapter_linux_amd64 api_adapter_windows_amd64.exe
echo "Cleanup done"

echo "=== Building Linux amd64 ==="
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o api_adapter_linux_amd64 .
echo "Linux amd64 build done: api_adapter_linux_amd64"

echo "=== Building Windows amd64 ==="
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o api_adapter_windows_amd64.exe .
echo "Windows amd64 build done: api_adapter_windows_amd64.exe"

echo "=== Build complete ==="