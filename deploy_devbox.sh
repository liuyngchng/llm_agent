cd project
rm *.py *.sh *.db
rm -fr resources/ templates/ static/ *.log __pycache__/ cert/ faiss_index/
cd ..
tar -xf llm_agent.tar
mv llm_agent/* project