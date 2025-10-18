#!/bin/bash
# deploy app in dev box on seal os
sudo ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
cd project
rm *.py *.sh *.db *.log
rm -fr resources/ templates/ static/ __pycache__/ cert/ faiss_index/  faiss_oa_vector/ hack/ sh/ upload_doc/
cd ..
tar -xf llm_agent.tar
mv llm_agent/* project
rm -fr llm_agent
echo 'deploy dev_box finish, app in dir ./project, have fun'