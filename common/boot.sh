/bin/bash -c 'source ../llm_py_env/bin/activate'
# for start application in docker container
APP="${APP_NAME:-http_chat}"
echo "start app: ${APP}"
echo "current dir $(pwd)"
echo "Python dir: $(which python)"
echo "ENV PYTHONPATH=${PYTHONPATH}"
echo "ENV DM_HOME=${DM_HOME}"
echo "ENV LD_LIBRARY_PATH=${LD_LIBRARY_PATH}"
#nohup /opt/llm_py_env/bin/gunicorn --timeout 240 --preload -w 4 -b 0.0.0.0:19000 http_service:app > server.log &2>&1 &
# for HTTP
#/opt/llm_py_env/bin/gunicorn --timeout 240 -w 1 --threads 8 -b 0.0.0.0:19000 apps.${APP}.app:app
# for HTTPS
# 根据 APP 名称选择不同的启动方式
if [ "${APP}" = "embedding" ]; then
    echo "检测到 embedding 应用，使用 Uvicorn 启动..."
    # 使用 Uvicorn 启动 FastAPI 应用
    CMD="/opt/llm_py_env/bin/uvicorn \
        --host 0.0.0.0 \
        --port 19000 \
        --workers 1 \
        --ssl-certfile ./common/cert/srv.crt \
        --ssl-keyfile ./common/cert/srv.key \
        apps.${APP}.app:app"
else
    echo "使用 Gunicorn 启动 ${APP} 应用..."
    # 其他应用使用 Gunicorn
    CMD="/opt/llm_py_env/bin/gunicorn \
        --certfile ./common/cert/srv.crt \
        --keyfile ./common/cert/srv.key \
        --timeout 240 \
        -w 1 \
        --threads 8 \
        -b 0.0.0.0:19000 \
        apps.${APP}.app:app"
fi

echo "exec_cmd: ${CMD}"
eval "${CMD}"
