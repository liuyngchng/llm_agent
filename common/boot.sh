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
CMD="/opt/llm_py_env/bin/gunicorn \
   --certfile ./common/cert/srv.crt \
   --keyfile ./common/cert/srv.key \
   --timeout 240 \
   -w 1 \
   --threads 8 \
   -b 0.0.0.0:19000 \
   apps.${APP}.app:app"
echo "exec_cmd: ${CMD}"
eval "${CMD}"
