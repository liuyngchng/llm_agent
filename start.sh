/bin/bash -c 'source ../llm_py_env/bin/activate'
echo "current dir `pwd`"
#nohup /opt/llm_py_env/bin/gunicorn --timeout 240 --preload -w 4 -b 0.0.0.0:19000 http_service:app > server.log &2>&1 &
/opt/llm_py_env/bin/gunicorn --timeout 240 --preload -w 4 -b 0.0.0.0:19000 http_nl2sql:app
