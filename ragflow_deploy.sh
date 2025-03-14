docker stop ragflow
docker rm ragflow
docker run -dit \
  -v /home/rd/workspace/ragflow:/ragflow \
  --name ragflow \
  --network host \
  ragflow:v0.12.0
docker logs -f ragflow