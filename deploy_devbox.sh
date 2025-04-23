cd project
rm *.py *.sh *.db *.log
rm -fr resources/ templates/ static/ __pycache__/ cert/ faiss_index/
cd ..
tar -xf llm_agent.tar
mv llm_agent/* project