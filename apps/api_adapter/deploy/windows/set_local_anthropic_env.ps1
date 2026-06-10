# 动态获取脚本名称和路径
$ScriptName = Split-Path -Leaf $MyInvocation.MyCommand.Path
$ScriptPath = Resolve-Path $MyInvocation.MyCommand.Path

# 检查是否以管理员权限运行（可选，某些环境可能需要）
# 注意：PowerShell 中设置环境变量不需要像 bash 那样 source，直接运行即可

Write-Host "正在执行: $ScriptName"

# 检查 LOCAL_LLM_API_KEY 环境变量
if (-not $env:LOCAL_LLM_API_KEY) {
    Write-Host "❌ 错误: LOCAL_LLM_API_KEY 环境变量未设置" -ForegroundColor Red
    exit 1
} else {
    Write-Host "LOCAL_LLM_API_KEY 已设置: $($env:LOCAL_LLM_API_KEY)" -ForegroundColor Green
}

# 探测 16001 端口服务是否启动
Write-Host "正在检查 127.0.0.1:16001 端口服务..."
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connection = $tcpClient.BeginConnect("127.0.0.1", 16001, $null, $null)
    $success = $connection.AsyncWaitHandle.WaitOne(3000)  # 3秒超时
    if ($success) {
        $tcpClient.EndConnect($connection)
        Write-Host "✅ 端口 16001 服务已启动" -ForegroundColor Green
    } else {
        throw "连接超时"
    }
    $tcpClient.Close()
} catch {
    Write-Host "❌ 错误: 端口 16001 服务未启动或无法连接" -ForegroundColor Red
    exit 1
}

# 设置环境变量（当前会话）
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:16001"
$env:ANTHROPIC_AUTH_TOKEN = $env:LOCAL_LLM_API_KEY
$env:API_TIMEOUT_MS = "600000"
$env:ANTHROPIC_MODEL = "deepseek-chat"
$env:ANTHROPIC_SMALL_FAST_MODEL = "deepseek-chat"

Write-Host "✅ 本地 ANTHROPIC 环境变量设置完成" -ForegroundColor Green

# 可选：设置为永久环境变量（取消注释以下行）
# [Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:16001", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", $env:LOCAL_LLM_API_KEY, "User")
# [Environment]::SetEnvironmentVariable("API_TIMEOUT_MS", "600000", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_MODEL", "deepseek-chat", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_SMALL_FAST_MODEL", "deepseek-chat", "User")