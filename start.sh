/bin/bash -c 'source ../llm_py_env/bin/activate'
echo "dir `pwd`"
#nohup gunicorn --timeout 240 --preload -w 4 -b  0.0.0.0:19000 http_rag:app > server.log &2>&1 &
gunicorn --timeout 240 --preload -w 4 -b  0.0.0.0:19000 http_rag:app
