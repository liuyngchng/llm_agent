#!/bin/bash
MODULE=http_rag
#MODULE=http_nl2sql
echo 'starting module '${MODULE}
/bin/bash -c 'source ../llm_py_env/bin/activate'
../llm_py_env/bin/gunicorn --timeout 240 -w 1 --threads 8 -b 0.0.0.0:19000 ${MODULE}:app
echo "module ${MODULE} stared"