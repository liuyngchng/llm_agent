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
    echo ? 虚拟环境不存在，请先运行 install.bat
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "%PROJECT_DIR%\cfg.yml" (
    echo ??  配置文件不存在，运行配置助手...
    call "%VENV_DIR%\Scripts\activate.bat"
    cd /d "%PROJECT_DIR%"
    "%VENV_DIR%\Scripts\python.exe" config_helper.py
    echo.
    echo 请按任意键继续启动...
    pause >nul
)

:: 直接使用虚拟环境的Python，不激活环境
cd /d "%PROJECT_DIR%"

:: 应用选择菜单
echo ========================================
echo  选择要启动的应用
echo ========================================
echo  1. chat - 知识库问答
echo  2. chat2db - 数据查询
echo  3. docx - 文档创作
echo  4. paper_review - AI评委
echo.

:SELECT_APP
set /p APP_CHOICE=请选择应用编号 (1-4): 
if "%APP_CHOICE%"=="1" (
    set APP_NAME=chat
    set APP_DESC=知识库问答
    set APP_PORT=19000
) else if "%APP_CHOICE%"=="2" (
    set APP_NAME=chat2db
    set APP_DESC=数据查询
    set APP_PORT=19001
) else if "%APP_CHOICE%"=="3" (
    set APP_NAME=docx
    set APP_DESC=文档创作
    set APP_PORT=19002
) else if "%APP_CHOICE%"=="4" (
    set APP_NAME=paper_review
    set APP_DESC=AI评委
    set APP_PORT=19003
) else (
    echo 无效选择，请重新输入！
    goto SELECT_APP
)

echo 已选择: %APP_NAME% - %APP_DESC%
echo.

:: 启动选中的应用
echo ========================================
echo  启动 %APP_DESC%
echo ========================================
echo ?? 启动中...
echo ?? 访问地址: http://127.0.0.1:%APP_PORT%
echo ??  停止方法: 按 Ctrl+C
echo ========================================
echo.

"%VENV_DIR%\Scripts\python.exe" -m apps.%APP_NAME%.app

echo.
echo 应用已退出
pause