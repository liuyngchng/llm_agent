@echo off
setlocal

set WORKSPACE=C:\workspace
set VENV_DIR=%WORKSPACE%\llm_py_env
set PROJECT_DIR=%WORKSPACE%\gitee_llm_agent-master

echo ========================================
echo   启动 LLM Agent
echo ========================================
echo.

:: 检查虚拟环境
if not exist "%VENV_DIR%" (
    echo ❌ 虚拟环境不存在，请先运行 install.bat
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "%PROJECT_DIR%\cfg.yml" (
    echo ⚠️  配置文件不存在，运行配置助手...
    call "%VENV_DIR%\Scripts\activate.bat"
    cd /d "%PROJECT_DIR%"
    python config_helper.py
    echo.
    echo 请按任意键继续启动...
    pause >nul
)

:: 激活环境并启动
call "%VENV_DIR%\Scripts\activate.bat"
cd /d "%PROJECT_DIR%"

echo 🚀 启动应用中...
echo 📍 启动后访问: http://127.0.0.1:19000
echo ⏹️  按 Ctrl+C 停止应用
echo.

python -m apps.chat.app

pause