@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   LLM Agent 自动化安装脚本
echo ========================================
echo.

:: 检查是否以管理员身份运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo 请以管理员身份运行此脚本！
    pause
    exit /b 1
)

:: 设置工作目录
set WORKSPACE=C:\workspace
set PROJECT_DIR=%WORKSPACE%\gitee_llm_agent-master
set VENV_DIR=%WORKSPACE%\llm_py_env
set DOWNLOAD_URL=https://gitee.com/liuyngchng/gitee_llm_agent/repository/archive/master.zip

:: 创建工作目录
echo [1/8] 创建工作目录...
if not exist "%WORKSPACE%" (
    mkdir "%WORKSPACE%"
    echo   已创建工作目录: %WORKSPACE%
) else (
    echo   工作目录已存在: %WORKSPACE%
)

:: 检查Python安装
echo [2/8] 检查Python环境...
python -V >nul 2>&1
if %errorLevel% neq 0 (
    echo   未检测到Python，请先安装Python 3.12.3
    echo   下载地址: https://www.python.org/downloads/release/python-3123/
    pause
    exit /b 1
)

python -c "import sys; print('   Python版本:' + sys.version)" 2>nul
pip -V >nul 2>&1
if %errorLevel% eq 0 (
    echo   pip已安装
) else (
    echo   pip未正确安装
    pause
    exit /b 1
)

:: 下载项目代码
echo [3/8] 下载项目源代码...
cd /d "%WORKSPACE%"
if exist "%PROJECT_DIR%" (
    echo   项目目录已存在，跳过下载
) else (
    powershell -Command "Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile 'gitee_llm_agent-master.zip'"
    if exist "gitee_llm_agent-master.zip" (
        powershell -Command "Expand-Archive -Path 'gitee_llm_agent-master.zip' -DestinationPath '.' -Force"
        del gitee_llm_agent-master.zip
        echo   源代码下载解压完成
    ) else (
        echo   下载失败，请检查网络连接
        pause
        exit /b 1
    )
)

:: 创建虚拟环境
echo [4/8] 创建Python虚拟环境...
if exist "%VENV_DIR%" (
    echo   虚拟环境已存在，跳过创建
) else (
    pip install virtualenv --quiet
    virtualenv "%VENV_DIR%"
    echo   虚拟环境创建完成: %VENV_DIR%
)

:: 激活虚拟环境并安装依赖
echo [5/8] 安装项目依赖包...
call "%VENV_DIR%\Scripts\activate.bat"
cd /d "%PROJECT_DIR%"
pip install -r requirements.txt --quiet
echo   依赖包安装完成

:: 配置应用（以chat应用为例）
echo [6/8] 配置应用程序...
set APP_NAME=chat
set APP_DIR=%PROJECT_DIR%\apps\%APP_NAME%

if exist "!APP_DIR!\cfg.db.template" (
    copy "!APP_DIR!\cfg.db.template" "cfg.db" >nul
    echo   已创建 cfg.db
)

if exist "!APP_DIR!\cfg.yml.template" (
    copy "!APP_DIR!\cfg.yml.template" "cfg.yml" >nul
    echo   已创建 cfg.yml
)

if exist "!APP_DIR!\logging.conf" (
    copy "!APP_DIR!\logging.conf" "logging.conf" >nul
    echo   已创建 logging.conf
)

:: 创建启动脚本
echo [7/8] 创建启动脚本...
echo @echo off > "%WORKSPACE%\start_agent.bat"
echo call "%VENV_DIR%\Scripts\activate.bat" >> "%WORKSPACE%\start_agent.bat"
echo cd /d "%PROJECT_DIR%" >> "%WORKSPACE%\start_agent.bat"
echo python -m apps.%APP_NAME%.app >> "%WORKSPACE%\start_agent.bat"
echo pause >> "%WORKSPACE%\start_agent.bat"

:: 完成提示
echo [8/8] 安装完成！
echo.
echo ========================================
echo 安装总结:
echo   工作目录: %WORKSPACE%
echo   项目目录: %PROJECT_DIR%
echo   虚拟环境: %VENV_DIR%
echo   启动脚本: %WORKSPACE%\start_agent.bat
echo.
echo 下一步操作:
echo   1. 编辑配置文件: %PROJECT_DIR%\cfg.yml
echo   2. 配置大模型API密钥
echo   3. 运行 start_agent.bat 启动应用
echo   4. 浏览器访问: http://127.0.0.1:19000
echo ========================================
echo.

pause