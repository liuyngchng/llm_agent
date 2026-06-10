# 动态获取脚本名称和路径
$ScriptName = Split-Path -Leaf $MyInvocation.MyCommand.Path
$ScriptPath = Resolve-Path $MyInvocation.MyCommand.Path

Write-Host "正在执行: $ScriptName"

# 检查 DEEPSEEK_API_KEY 环境变量
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Host "❌ 错误: DEEPSEEK_API_KEY 环境变量未设置" -ForegroundColor Red
    exit 1
} else {
    Write-Host "DEEPSEEK_API_KEY 已设置: $($env:DEEPSEEK_API_KEY)" -ForegroundColor Green
}

# 设置环境变量（当前会话）
$env:ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
$env:ANTHROPIC_AUTH_TOKEN = $env:DEEPSEEK_API_KEY
$env:API_TIMEOUT_MS = "600000"
$env:ANTHROPIC_MODEL = "deepseek-v4-pro"
$env:ANTHROPIC_SMALL_FAST_MODEL = "deepseek-v4-flash"
# 防止联网验证、模型回退、检查更新失败导致的卡顿或错误
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
# 关闭计费头,加速推理
$env:CLAUDE_CODE_ATTRIBUTION_HEADER = "0"

Write-Host "✅ 公有 ANTHROPIC 环境变量设置完成" -ForegroundColor Green

# 可选：设置为永久环境变量（取消注释以下行）
# [Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_AUTH_TOKEN", $env:DEEPSEEK_API_KEY, "User")
# [Environment]::SetEnvironmentVariable("API_TIMEOUT_MS", "600000", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_MODEL", "deepseek-v4-pro", "User")
# [Environment]::SetEnvironmentVariable("ANTHROPIC_SMALL_FAST_MODEL", "deepseek-v4-flash", "User")
# [Environment]::SetEnvironmentVariable("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1", "User")
# [Environment]::SetEnvironmentVariable("CLAUDE_CODE_ATTRIBUTION_HEADER", "0", "User")