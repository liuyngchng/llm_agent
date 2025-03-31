import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_ollama import ChatOllama

import logging.config

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

def get_data(line_txt):
    model = ChatOllama(model="deepseek-r1", base_url="http://127.0.0.1:11434", temperature=0)
    template = """请生成严格遵循如下结构的纯JSON数组（不要任何非JSON内容）：：
    [{{"q":"问题1","a":"答案1"}},{{"q":"问题2","a":"答案2"}}]
    注意：1. 必须是合法JSON 2. 禁止注释 3. 使用双引号
         2. 不要输出 <think> </think>所包含的内容，直接给出最终结果
         3. 禁用注释/代码块,确保数组闭合
    输入文本：{question}"""
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | model | RunnableLambda(lambda x: x.content)
    response = chain.invoke({
        "question":f"请为以下文本生成10个不同提问角度的问题：{line_txt}"
    })
    logger.info(f"response: {response}")
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)}")
        return []


if __name__  == "__main__":
    txt = "昆仑燃气需要服务1500万终端客户"
    result = get_data(txt)
    if result:
        logger.info(f"\n{result}\n")
        logger.info(result[0]["q"])
    else:
        logger.warning("未生成有效数据")