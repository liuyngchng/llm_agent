/bin/bash -c 'source ../llm_py_env/bin/activate'
# for start application in docker container
#MODULE=http_nl2sql
MODULE=http_rag
echo "current dir `pwd`"
#nohup /opt/llm_py_env/bin/gunicorn --timeout 240 --preload -w 4 -b 0.0.0.0:19000 http_service:app > server.log &2>&1 &
# just for simplicity to deploy and share memory
/opt/llm_py_env/bin/gunicorn --timeout 240 -w 1 --threads 8 -b 0.0.0.0:19000 ${MODULE}:app
# real production environment
#/opt/llm_py_env/bin/gunicorn --timeout 240 --preload -w 4 -b 0.0.0.0:19000 ${MODULE}:app
