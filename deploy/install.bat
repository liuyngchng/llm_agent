@echo off
setlocal enabledelayedexpansion

:: 设置工作目录和日志文件
set WORKSPACE=C:\workspace
set LOG_FILE=%WORKSPACE%\install_log_%DATE:~0,4%_%DATE:~5,2%_%DATE:~8,2%.txt
set PIP_LOG=%WORKSPACE%\pip_install_log.txt

:: 创建工作目录
if not exist "%WORKSPACE%" (
    mkdir "%WORKSPACE%"
)

echo ======================================== > "%LOG_FILE%"
echo   LLM Agent 自动化安装脚本日志 >> "%LOG_FILE%"
echo   开始时间: %DATE% %TIME% >> "%LOG_FILE%"
echo   主日志文件: %LOG_FILE% >> "%LOG_FILE%"
echo   PIP安装日志: %PIP_LOG% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

:: 显示日志文件位置
echo ========================================
echo  LLM Agent 自动化安装脚本
echo ========================================
echo.
echo 安装进度日志文件:
echo   %LOG_FILE%
echo.
echo PIP安装详细日志:
echo   %PIP_LOG%
echo.
echo 请保持窗口打开，安装过程中可查看日志文件了解进度
echo.
echo 按任意键开始安装...
pause >nul
echo.

:: 同时输出到屏幕和日志
call :LOG "========================================"
call :LOG "  LLM Agent 自动化安装脚本"
call :LOG "========================================"
call :LOG "主日志文件: %LOG_FILE%"
call :LOG "PIP安装日志: %PIP_LOG%"
call :LOG ""

:: 检查是否以管理员身份运行
call :LOG "检查管理员权限..."
net session >nul 2>&1
if !errorlevel! neq 0 (
    call :LOG "错误: 请以管理员身份运行此脚本！"
    echo 错误: 请以管理员身份运行此脚本！
    pause
    exit /b 1
)
call :LOG "管理员权限确认"

:: 设置其他目录
set PROJECT_DIR=%WORKSPACE%\gitee_llm_agent-master
set VENV_DIR=%WORKSPACE%\llm_py_env
set DOWNLOAD_URL=https://gitee.com/liuyngchng/gitee_llm_agent/repository/archive/master.zip
set ZIP_FILE=%WORKSPACE%\gitee_llm_agent-master.zip

call :LOG "工作目录设置: %WORKSPACE%"
call :LOG "项目目录: %PROJECT_DIR%"
call :LOG "虚拟环境目录: %VENV_DIR%"

:: 创建工作目录
call :LOG "[1/8] 创建工作目录..."
if not exist "%WORKSPACE%" (
    mkdir "%WORKSPACE%"
    if !errorlevel! == 0 (
        call :LOG "   已创建工作目录: %WORKSPACE%"
    ) else (
        call :LOG "   错误: 创建目录失败: %WORKSPACE%"
        echo 错误: 创建目录失败: %WORKSPACE%
        pause
        exit /b 1
    )
) else (
    call :LOG "   工作目录已存在: %WORKSPACE%"
)

:: 检查Python安装
call :LOG "[2/8] 检查Python环境..."
python --version >nul 2>&1
if !errorlevel! neq 0 (
    call :LOG "   错误: 未检测到Python，请先安装Python 3.12.3"
    echo 错误: 未检测到Python，请先安装Python 3.12.3
    echo 下载地址: https://www.python.org/downloads/release/python-3123/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
call :LOG "   %PYTHON_VERSION%"
echo   检测到: %PYTHON_VERSION%

pip --version >nul 2>&1
if !errorlevel! == 0 (
    call :LOG "   pip已安装"
    echo   pip已安装
) else (
    call :LOG "   错误: pip未正确安装"
    echo 错误: pip未正确安装
    pause
    exit /b 1
)

:: 手动下载步骤
call :LOG "[3/8] 准备下载项目源代码..."
echo [3/8] 准备下载项目源代码...
if not exist "%PROJECT_DIR%" (
    call :LOG "   需要手动下载项目源代码"
    
    :: 显示手动下载指引
    echo.
    echo ========================================
    echo  手动下载指引
    echo ========================================
    echo.
    echo 由于网站下载验证，需要您手动下载项目文件：
    echo.
    echo 步骤1: 打开浏览器
    echo 步骤2: 访问: %DOWNLOAD_URL%
    echo 步骤3: 如果有验证，请完成验证后下载ZIP文件
    echo 步骤4: 将下载的文件保存为: %ZIP_FILE%
    echo.
    echo 下载完成后，请确保文件存在于此位置：
    echo   %ZIP_FILE%
    echo.
    echo 按任意键继续（确保文件已下载完成）...
    pause
    
    :: 检查文件是否存在
    call :LOG "   检查手动下载的文件..."
    if not exist "%ZIP_FILE%" (
        call :LOG "   错误: 文件不存在，请确保已下载并保存到正确位置"
        echo.
        echo 错误: 未找到文件 %ZIP_FILE%
        echo 请确保已完成手动下载并将文件保存到上述位置
        echo.
        pause
        exit /b 1
    )
    
    :: 检查文件大小
    for %%F in ("%ZIP_FILE%") do set FILE_SIZE=%%~zF
    call :LOG "   下载文件大小: !FILE_SIZE! 字节"
    echo   下载文件大小: !FILE_SIZE! 字节
    
    if !FILE_SIZE! LSS 10000 (
        call :LOG "   警告: 文件大小异常小，可能下载不完整"
        echo.
        echo 警告: 文件大小只有 !FILE_SIZE! 字节，可能下载不完整
        choice /C YN /M "是否继续解压？(Y-继续/N-重新下载)"
        if !errorlevel! == 2 (
            call :LOG "   用户选择重新下载"
            echo 请重新下载文件，然后再次运行安装脚本
            pause
            exit /b 1
        )
    )
    
    call :LOG "   开始解压文件..."
    echo   开始解压文件...
    
    :: 解压文件
    powershell -Command "try { Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%WORKSPACE%' -Force; exit 0 } catch { exit 1 }"
    
    if !errorlevel! == 0 (
        del "%ZIP_FILE%"
        call :LOG "   源代码解压完成"
        call :LOG "   项目目录: %PROJECT_DIR%"
        echo   解压成功！
    ) else (
        call :LOG "   错误: 解压失败，ZIP文件可能已损坏"
        echo.
        echo 错误: 解压失败！
        echo 可能的原因：
        echo   - 文件下载不完整
        echo   - 文件已损坏
        echo   - 网络问题导致文件错误
        echo.
        echo 请重新下载文件，然后再次运行安装脚本
        pause
        exit /b 1
    )
) else (
    call :LOG "   项目目录已存在，跳过下载"
    echo   项目目录已存在，跳过下载
)

:: 创建虚拟环境
call :LOG "[4/8] 创建Python虚拟环境..."
echo [4/8] 创建Python虚拟环境...
if exist "%VENV_DIR%" (
    call :LOG "   虚拟环境已存在，跳过创建"
    echo   虚拟环境已存在，跳过创建
) else (
    call :LOG "   安装 virtualenv..."
    echo   安装 virtualenv...
    pip install virtualenv --quiet
    if !errorlevel! neq 0 (
        call :LOG "   错误: virtualenv 安装失败"
        echo 错误: virtualenv 安装失败
        pause
        exit /b 1
    )
    
    call :LOG "   创建虚拟环境到: %VENV_DIR%"
    echo   创建虚拟环境到: %VENV_DIR%
    virtualenv "%VENV_DIR%"
    if !errorlevel! == 0 (
        call :LOG "   虚拟环境创建完成: %VENV_DIR%"
        echo   虚拟环境创建完成
    ) else (
        call :LOG "   错误: 虚拟环境创建失败"
        echo 错误: 虚拟环境创建失败
        pause
        exit /b 1
    )
)

:: 激活虚拟环境并安装依赖
call :LOG "[5/8] 安装项目依赖包..."
echo [5/8] 安装项目依赖包...
call "%VENV_DIR%\Scripts\activate.bat"
cd /d "%PROJECT_DIR%"
if exist "requirements.txt" (
    call :LOG "   开始安装依赖包，这可能需要较长时间..."
    echo.
    echo ========================================
    echo  正在安装Python依赖包
    echo ========================================
    echo.
    echo 这可能需要10-30分钟，具体取决于网络速度...
    echo.
    echo 详细安装进度请查看日志文件:
    echo   %PIP_LOG%
    echo.
    echo 请耐心等待，不要关闭此窗口...
    echo.
    
    call :LOG "   PIP安装详细日志: %PIP_LOG%"
    
    :: 删除可能存在的旧日志文件，避免权限冲突
    if exist "%PIP_LOG%" (
        del "%PIP_LOG%"
    )
    
    :: 安装依赖包并记录详细日志（使用追加模式避免权限冲突）
    echo 开始安装依赖包，时间: %TIME% >> "%PIP_LOG%"
    echo ======================================== >> "%PIP_LOG%"
    
    :: 使用tee命令模拟同时输出到屏幕和文件（如果可用），否则只记录到文件
    where tee >nul 2>&1
    if !errorlevel! == 0 (
        echo 使用tee命令记录日志...
        pip install -r requirements.txt 2>&1 | tee -a "%PIP_LOG%"
    ) else (
        echo 使用标准输出记录日志...
        pip install -r requirements.txt >> "%PIP_LOG%" 2>&1
    )
    
    :: 检查安装结果
    if !errorlevel! == 0 (
        call :LOG "   依赖包安装完成"
        echo   依赖包安装完成！
        echo   详细日志已保存到: %PIP_LOG%
    ) else (
        call :LOG "   错误: 依赖包安装失败"
        call :LOG "   请查看PIP安装日志: %PIP_LOG%"
        echo.
        echo 错误: 依赖包安装失败！
        echo 请查看详细错误日志: %PIP_LOG%
        echo.
        echo 或手动运行以下命令查看错误：
        echo   call "%VENV_DIR%\Scripts\activate.bat"
        echo   cd /d "%PROJECT_DIR%"
        echo   pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    call :LOG "   错误: requirements.txt 文件不存在"
    call :LOG "   请检查项目目录是否正确: %PROJECT_DIR%"
    echo.
    echo 错误: 未找到 requirements.txt 文件
    echo 项目目录内容：
    dir "%PROJECT_DIR%" /B
    echo.
    pause
    exit /b 1
)

:: 配置应用 - 让用户选择
call :LOG "[6/8] 配置应用程序..."
echo [6/8] 配置应用程序...
echo.
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
) else if "%APP_CHOICE%"=="2" (
    set APP_NAME=chat2db
    set APP_DESC=数据查询
) else if "%APP_CHOICE%"=="3" (
    set APP_NAME=docx
    set APP_DESC=文档创作
) else if "%APP_CHOICE%"=="4" (
    set APP_NAME=paper_review
    set APP_DESC=AI评委
) else (
    echo 无效选择，请重新输入！
    goto SELECT_APP
)

call :LOG "   用户选择应用: %APP_NAME% - %APP_DESC%"
echo 已选择: %APP_NAME% - %APP_DESC%
echo.

set APP_DIR=%PROJECT_DIR%\apps\%APP_NAME%

if not exist "%APP_DIR%" (
    call :LOG "   错误: 应用目录不存在: %APP_DIR%"
    call :LOG "   可用的应用目录:"
    dir "%PROJECT_DIR%\apps" /B
    echo.
    echo 错误: 应用目录不存在: %APP_DIR%
    echo 可用的应用目录：
    dir "%PROJECT_DIR%\apps" /B
    echo.
    pause
    exit /b 1
)

call :LOG "   配置应用: %APP_NAME%"

if exist "%APP_DIR%\cfg.db.template" (
    copy "%APP_DIR%\cfg.db.template" "%PROJECT_DIR%\cfg.db" >nul
    call :LOG "   已创建 cfg.db"
) else (
    call :LOG "   警告: cfg.db.template 不存在"
)

if exist "%APP_DIR%\cfg.yml.template" (
    copy "%APP_DIR%\cfg.yml.template" "%PROJECT_DIR%\cfg.yml" >nul
    call :LOG "   已创建 cfg.yml"
) else (
    call :LOG "   警告: cfg.yml.template 不存在"
)

if exist "%APP_DIR%\logging.conf" (
    copy "%APP_DIR%\logging.conf" "%PROJECT_DIR%\logging.conf" >nul
    call :LOG "   已创建 logging.conf"
) else (
    call :LOG "   警告: logging.conf 不存在"
)

:: 创建启动脚本
call :LOG "[7/8] 创建启动脚本..."
echo [7/8] 创建启动脚本...
(
echo @echo off
echo echo ========================================
echo echo   LLM Agent 启动脚本 - %APP_DESC%
echo echo ========================================
echo echo.
echo call "%VENV_DIR%\Scripts\activate.bat"
echo cd /d "%PROJECT_DIR%"
echo echo 启动应用: %APP_NAME% - %APP_DESC%
echo echo 访问地址: http://127.0.0.1:19000
echo echo 按 Ctrl+C 停止应用
echo echo.
echo python -m apps.%APP_NAME%.app
echo pause
) > "%WORKSPACE%\start_agent.bat"

if exist "%WORKSPACE%\start_agent.bat" (
    call :LOG "   启动脚本已创建: %WORKSPACE%\start_agent.bat"
    echo   启动脚本已创建: %WORKSPACE%\start_agent.bat
) else (
    call :LOG "   错误: 启动脚本创建失败"
    echo 错误: 启动脚本创建失败
)

:: 完成提示
call :LOG "[8/8] 安装完成！"
echo [8/8] 安装完成！
call :LOG ""
call :LOG "========================================"
call :LOG "安装总结:"
call :LOG "  工作目录: %WORKSPACE%"
call :LOG "  项目目录: %PROJECT_DIR%"
call :LOG "  虚拟环境: %VENV_DIR%"
call :LOG "  启动应用: %APP_NAME% - %APP_DESC%"
call :LOG "  启动脚本: %WORKSPACE%\start_agent.bat"
call :LOG "  主日志文件: %LOG_FILE%"
call :LOG "  PIP安装日志: %PIP_LOG%"
call :LOG ""
call :LOG "下一步操作:"
call :LOG "  1. 编辑配置文件: %PROJECT_DIR%\cfg.yml"
call :LOG "  2. 配置大模型API密钥"
call :LOG "  3. 运行 start_agent.bat 启动应用"
call :LOG "  4. 浏览器访问: http://127.0.0.1:19000"
call :LOG "========================================"
call :LOG ""

echo.
echo ========================================
echo  安装完成！
echo ========================================
echo.
echo 工作目录: %WORKSPACE%
echo 项目目录: %PROJECT_DIR%
echo 虚拟环境: %VENV_DIR%
echo 启动应用: %APP_NAME% - %APP_DESC%
echo 启动脚本: %WORKSPACE%\start_agent.bat
echo.
echo 安装日志文件:
echo   主日志: %LOG_FILE%
echo   PIP安装日志: %PIP_LOG%
echo.
echo 下一步操作:
echo 1. 编辑配置文件: %PROJECT_DIR%\cfg.yml
echo 2. 配置大模型API密钥
echo 3. 运行 start_agent.bat 启动应用
echo 4. 浏览器访问: http://127.0.0.1:19000
echo.
echo 按任意键关闭此窗口...
pause >nul

goto :EOF

:LOG
echo %* >> "%LOG_FILE%"
echo %*
goto :EOF