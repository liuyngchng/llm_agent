#!/bin/bash
source ./bin/activate
gunicorn --timeout 240 -w 1 --threads 8 -b 0.0.0.0:19000 http_rag:app