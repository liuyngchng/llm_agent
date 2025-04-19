docker stop llm_nl2sql
docker rm llm_nl2sql
#docker run -dit --name llm_nl2sql --network host --rm \
docker run -dit --name llm_nl2sql  \
  --security-opt seccomp=unconfined \
  -v /data/llm_agent:/opt/app \
  -p 19001:19000 \
  llm_nl2sql:1.1
