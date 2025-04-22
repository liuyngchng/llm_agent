#!/bin/bash
# for start application in local bare metal
# default module name is http_rag, user can customized the argument
MODULE=${1:-http_rag}
# delete de suffix '.py'
MODULE=${MODULE%.py}
# you can go to module dir here
#cd 'module_dir'
echo 'starting module '${MODULE}
# active the virtual env for python, or you can hardcode your env python location
source ../llm_py_env/bin/activate
# start your module with gunicorn WSGI
gunicorn --timeout 240 -w 1 --threads 8 -b 0.0.0.0:19000 ${MODULE}:app
