@echo off
setlocal

set WORKSPACE=C:\workspace

echo ========================================
echo   LLM Agent 卸载脚本
echo ========================================
echo.

choice /C YN /M "确定要完全卸载LLM Agent吗？这将删除所有相关文件"
if errorlevel 2 (
    echo 卸载已取消
    pause
    exit /b 0
)

echo 正在卸载...
if exist "%WORKSPACE%\llm_py_env" (
    rmdir /s /q "%WORKSPACE%\llm_py_env"
    echo ✅ 已删除虚拟环境
)

if exist "%WORKSPACE%\gitee_llm_agent-master" (
    rmdir /s /q "%WORKSPACE%\gitee_llm_agent-master"
    echo ✅ 已删除项目文件
)

if exist "%WORKSPACE%\start_agent.bat" (
    del "%WORKSPACE%\start_agent.bat"
    echo ✅ 已删除启动脚本
)

echo.
echo 🎉 卸载完成！
pause