#!/bin/bash
set -e

echo "=== 清理历史构建产物 ==="
rm -f api_adapter_linux_amd64 api_adapter_windows_amd64.exe
echo "清理完成"

echo "=== 开始构建 Linux amd64 ==="
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o api_adapter_linux_amd64 .
echo "Linux amd64 构建完成: api_adapter_linux_amd64"

echo "=== 开始构建 Windows amd64 ==="
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o api_adapter_windows_amd64.exe .
echo "Windows amd64 构建完成: api_adapter_windows_amd64.exe"

echo "=== 构建完成 ==="