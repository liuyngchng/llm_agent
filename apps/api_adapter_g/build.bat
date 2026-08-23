@echo off
setlocal

echo === Cleaning up previous build artifacts ===
if exist api_adapter_linux_amd64 del /f api_adapter_linux_amd64
if exist api_adapter_windows_amd64.exe del /f api_adapter_windows_amd64.exe
echo Cleanup done

echo === Building Linux amd64 ===
set CGO_ENABLED=0
set GOOS=linux
set GOARCH=amd64
go build -o api_adapter_linux_amd64 .
echo Linux amd64 build done: api_adapter_linux_amd64

echo === Building Windows amd64 ===
set CGO_ENABLED=0
set GOOS=windows
set GOARCH=amd64
go build -o api_adapter_windows_amd64.exe .
echo Windows amd64 build done: api_adapter_windows_amd64.exe

echo === Build complete ===
endlocal