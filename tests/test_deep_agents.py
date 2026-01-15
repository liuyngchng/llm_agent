import re
import os
from typing import Literal
from tavily import TavilyClient
from unittest import result
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

def internet_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general","news","finance" ]= "general",
        include_raw_content: bool = False,
        ):
    """
    运行网络搜索
    这是一个用于网络搜索的工具函数，封装了tavily的搜索功能
    参数说明：
    - query: 搜索查询字符串，例如“python异步编程教程”
    - max_results: 返回结果的最大数量，默认为5
    - topic: 搜索主题类型，可选"general","news"或"finance"，默认为"general"
    - include_raw_content: 是否包含原始网页，默认为False

    返回
    - 搜索结果字典，包括标题、url、摘要等信息
    """
    # 通过在网站 https://app.tavily.com/ 上注册用户获取
    tavily_key = "tvly-dev-your-tavily-key"
    tavily_client = TavilyClient(tavily_key)
    try:
        response = tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
            )
        return response
    except Exception as e:
        print(e)
        return None

 
def write_local_file(file_path: str, content: str) -> dict:  
    """  
    将内容写入本地文件  
    这是一个用于将内容保存到本地文件的工具函数。  
  
    参数说明：  
    - file_path: 文件路径，例如 "report.md" 或 "./reports/research_report.md"  
    - content: 要写入文件的内容（字符串）  
  
    返回：  
    - 包含操作结果的字典，如果成功则返回 {"status": "success", "file_path": file_path}  
    - 如果失败则返回 {"status": "error", "error": "错误信息"}  
    """  
    try:  
        # 确保目录存在  
        directory = os.path.dirname(file_path)  
        if directory and not os.path.exists(directory):  
            os.makedirs(directory, exist_ok=True)  
          
        # 写入文件  
        with open(file_path, 'w', encoding='utf-8') as f:  
            f.write(content)  
          
        return {  
            "status": "success",  
            "file_path": file_path,  
            "message": f"文件已成功保存到：{file_path}"  
        }  
    except Exception as e:  
        return {  
            "status": "error",  
            "error": f"写入文件失败：{str(e)}"  
        }  
    print("文件写入工具创建完成")


# 本程序为独立运行程序，仅进行Deepagents功能测试，不遵循langgraph和langsmith约定； 
if __name__ == '__main__':
    # print("开始测试搜索工具...")
    # test = internet_search("帮我检索一下Deeepagents框架的特点", max_results=5, topic="general")
    # print(f"搜索结果数量：{len(test.get('results', []))}")
    # #显示第一条结果
    # print("第一条结果：")
    # if test.get('results'):
    #     first = test["results"][0]
    #     print(f"标题：{first.get('title','N/A')}")
    #     print(f"URL：{first.get('url','N/A')}")
    #     print(f"摘要：{first.get('content','N/A')}")
    # else:
    #     print(f"没有搜索结果")

    model = init_chat_model(
        model_provider="deepseek",
        model="deepseek-chat",
        api_key="sk-your-deepseek-key", # api_key 通过在 http://platform.deepseek.com/ 上注册并充值获取
        base_url="https://api.deepseek.com",    
    )
    # print("开始LLM测试...")
    # question = "How do I use LangChain?"
    # result = model.invoke(question)
    # print(result.content)
    research_instructions = """
    你是一位资深的研究人员，你的工作是进行深入的研究，然后撰写一份精美的报告。
    你可以通过互联网搜索引擎作为主要的信息收集工具。

    ## `互联网搜索`
    使用此功能针对给定的查询进行网络搜索，你可以指定要返回的最大结果数量、主题以及是否包含原始内容。
    ## `写入本地文件`
    使用此功能将内容写入本地文件，当你完成研究报告后，使用此工具将完整报告保存到文件中。
    - 文件路径建议使用.md格式，例如"report.md"
    - 确保报告内容完整，结构清晰，包含所有章节和引用来源。

    在进行研究时：
    1、首先将研究任务分解为清晰的步骤；
    2、使用互联网搜索来收集全面的信息；
    3、如果内容太多，将重要内容保存到文件中；
    4、将信息整合成一份结构清晰的报告；
    5、务必引用你的资料来源。
    """
    agent = create_deep_agent(
        model=model,
        tools=[internet_search,write_local_file],
        system_prompt=research_instructions
    )
    # 使用agent.invoke模式，直接输出结果 
    # print("开始Deepagents测试...")
    # result = agent.invoke({"messages": [{"role": "user", "content": "帮我检索一下Deeepagents框架的特点"}]})
    # print(result["messages"][-1].content)  


    # 使用agent.debug模式，在terminal中实时打印所有事件
    import json
    from pyexpat.errors import messages
    import re
    from urllib import response
    from regex import T
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.json import JSON
    # 导入Rich库
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.markdown import Markdown
        from rich.json import JSON
        RICH_AVAILABLE = True
        console = Console()
        print("Rich库已安装，将使用美化输出样式")
    except ImportError:
        RICH_AVAILABLE = False
        console = None
        print("Rich库未安装，将使用默认输出样式")
    
    step_num = 0
    final_response = None

    # 执行debug并监控agent执行事件，实时流式输出
    for event in agent.stream(
        {"messages": [{"role": "user", "content":"帮我检索一下Deeepagents框架的特点"}]},
        stream_mode = "values"
    ):
        step_num+=1
        console.print(f"\n[bold yellow]{'-'*80}[/bold yellow]")
        console.print(f"[bold yellow]第{step_num}步[/bold yellow]")
        console.print(f"[bold yellow]{'-'*80}[/bold yellow]")

        if "messages" in event:
            messages = event["messages"]
            if messages:
                msg = messages[-1]
                #保存最终响应
                if hasattr(msg,"content") and msg.content and not hasattr(msg,'tool_calls'):
                    final_response = msg.content

                #IF AI思考事件
                if hasattr(msg,"content") and msg.content:
                    #如果内容太长，只显示前300字符作为预览
                    content = msg.content
                    if len(content) > 300 and not (hasattr(msg,'tool_calls') and msg.tool_calls):
                        preview = content[:300] + "..."
                        console.print(Panel(
                            f"{preview}\n\n[dim](内容较长，完整内容将在最后显示)[/dim]",
                            title="[bold green]AI思考[/bold green]",
                            border_style="green"
                        ))
                    else:
                        console.print(Panel(
                        content,
                        title="[bold green]AI思考[/bold green]",
                        border_style="green"
                        ))
                
                #IF 工具调用事件
                if hasattr(msg,"tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        tool_info = {
                            "工具名称":tool_call.get('name','unknown'),
                            "工具参数":tool_call.get('args',{})
                        }
                        console.print(Panel(
                        JSON(json.dumps(tool_info,ensure_ascii=False)),
                        title="[bold blue]工具调用[/bold blue]",
                        border_style="blue"
                        ))
                
                #IF 工具响应事件
                if hasattr(msg,"name") and msg.name:
                    response = str(msg.content)[:500]
                    if len(str(msg.content)) > 500:
                        response += f"\n...（共{len(str(msg.content))}个字符）"
                        console.print(Panel(
                            response,
                            title=f"[bold red]工具响应：{msg.name}[/bold red]",
                            border_style="red"
                        ))                
    console.print(f"\n [bold green]任务完成[/bold green]\n")
    
    
    
    
    
    
    
    
    
    
    
    
    
