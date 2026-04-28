import json
from typing import TypedDict, List, Optional, Any, Dict
import time
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import re
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from browser_manager import browser_manager
from prompt import execution_prompt
from tools import (
    click_element,
    fill_element,
    press_key,
    scroll_page,
    get_page_text,
    extract_text_from_selector,
    extract_attribute_from_selector,
    ask_human_help,
    analyze_page_with_som,
)


#USER_INPUT = "I want to find the best price for the iPhone 15 Pro Max 512GB. Please provide the price of the mobile at various e-commerce websites."
#USER_INPUT = "I want the vin decoding of the vin number 1HGCM82633A123456 in government websites"
MAX_RETRIES = 2
MAX_AGENT_STEPS = 10

llm = ChatOpenAI(
    model="gpt-oss-120b",
    api_key="your_api_key",
    base_url="https://api.sambanova.ai/v1"
)


tools = [
    click_element,
    fill_element,
    press_key,
    scroll_page,
    get_page_text,
    extract_text_from_selector,
    extract_attribute_from_selector,
    ask_human_help,
    analyze_page_with_som,
]

llm_with_tools = llm.bind_tools(tools)

from langchain_core.messages import ToolMessage
import traceback

def custom_tool_node(state):
    messages = state["messages"]
    last_message = messages[-1]
    responses = []
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f">>> EXECUTING TOOL: {tool_name} with args: {tool_args}")
            
            tool_obj = next((t for t in tools if t.name == tool_name), None)
            if tool_obj:
                try:
                    result = tool_obj.invoke(tool_args)
                    responses.append(ToolMessage(content=str(result), name=tool_name, tool_call_id=tool_call["id"]))
                except Exception as e:
                    traceback.print_exc()
                    responses.append(ToolMessage(content=f"Error executing tool: {e}", name=tool_name, tool_call_id=tool_call["id"]))
            else:
                responses.append(ToolMessage(content=f"Tool {tool_name} not found", name=tool_name, tool_call_id=tool_call["id"]))
                
    return {"messages": messages + responses}

tool_node = custom_tool_node


class ExecutionState(TypedDict):
    messages: List[Any]
    step_count: int
    result: Optional[str]


def agent_node(state: ExecutionState):
    print(f"\n--- AGENT STEP {state['step_count']} ---")
    if state["step_count"] >= MAX_AGENT_STEPS:
        print(">>> STOPPINg: Max agent steps reached.")
        return {"result": "Stopped: max steps reached."}

    max_retries = 3
    response = None
    
    for attempt in range(max_retries):
        try:
            response = llm_with_tools.invoke(
                [SystemMessage(content=execution_prompt)] + state["messages"]
            )
            break
        except Exception as e:
            print(f">>> LLM API ERROR (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(">>> Retrying in 5 seconds...")
                time.sleep(5)
            else:
                return {"result": f"Failed due to LLM API error: {e}"}
    
    print(f">>> AGENT RESPONSE CONTENT: {response.content}")
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f">>> AGENT TOOL CALLS: {response.tool_calls}")

    return {
        "messages": state["messages"] + [response],
        "step_count": state["step_count"] + 1
    }


def should_continue(state: ExecutionState):

    if state.get("result"):
        print(">>> ROUTING TO: final (result already set)")
        return "final"

    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(">>> ROUTING TO: tools")
        return "tools"

    print(">>> ROUTING TO: final (no tool calls found)")
    return "final"


def finalize(state: ExecutionState):
    return {"result": state["messages"][-1].content}


builder = StateGraph(ExecutionState)
builder.add_node("agent", agent_node)
builder.add_node("tools", tool_node)
builder.add_node("final", finalize)

builder.set_entry_point("agent")
builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "final": "final"
    }
)
builder.add_edge("tools", "agent")
builder.add_edge("final", END)

execution_graph = builder.compile()


def search_web(query: str) -> List[Dict]:
    print(">>> SEARCHING WEB...")
    tavily = TavilySearch(
        max_results=2,
        tavily_api_key="your_tavily_key"
    )
    results = tavily.invoke(query)

    if isinstance(results, dict) and "results" in results:
        return results["results"]
    if isinstance(results, list):
        return results
    return []


def execution_agent(url: str, user_input: str) -> str:

    print("\n=====================================")
    print(f">>> EXECUTING ON: {url}")
    print("=====================================\n")

    browser_manager.navigate(url)

    execution_query = f"""
User Task:
{user_input}

Current Website:
{url}

1. Call analyze_page_with_som FIRST.
2. Identify relevant fields/buttons.
3. Fill required inputs.
4. Submit form.
5. Extract only relevant results.
6. Return structured JSON.
"""

    result = execution_graph.invoke({
        "messages": [HumanMessage(content=execution_query)],
        "step_count": 0,
        "result": None
    })

    return result.get("result", "No result returned.")


final_results=[]

def orchestrator(user_input: str):

    state = {
        "urls": [],
        "site_names": [],
        "current_site_index": 0,
        "retry_count": 0,
        "aggregated_results": [],
        "done": False,
        "last_error": None,
    }


    search_results = search_web(user_input)

    for r in search_results:
        state["urls"].append(r["url"])
        state["site_names"].append(r.get("title", r["url"]))

    print(f">>> FOUND {len(state['urls'])} WEBSITES\n")


    while state["current_site_index"] < len(state["urls"]):

        url = state["urls"][state["current_site_index"]]

        try:
            result = execution_agent(url, user_input)

            print("\n----- RESULT -----\n")
            print(result)
            
            final_results.append(str(result))
            print("\n------------------\n")

            state["aggregated_results"].append(result)

            state["retry_count"] = 0
            state["current_site_index"] += 1

        except Exception as e:
            print(">>> ERROR:", str(e))

            state["retry_count"] += 1

            if state["retry_count"] >= MAX_RETRIES:
                print(">>> SKIPPING WEBSITE\n")
                state["retry_count"] = 0
                state["current_site_index"] += 1

    state["done"] = True
    browser_manager.close_browser()




    

    print("\n==============================")
    print("FINAL AGGREGATED RESULTS")
    print("==============================\n")

    for r in state["aggregated_results"]:
        print(r)
        print("\n")



def final_summarization(list_of_outputs: list,query: str):
        
    documents = [Document(page_content=t) for t in list_of_outputs]


    splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50
    )

    docs = splitter.split_documents(documents)



    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


    vector_store = FAISS.from_documents(docs, embeddings)

    retriever = vector_store.as_retriever(search_kwargs={"k": 3})


    prompt = ChatPromptTemplate.from_template(
    """
    You are a system that converts text into structured JSON.

    User Request:
    {question}

    Rules:
    - Keep context from each website
    - Output MUST be valid JSON
    - Do not include explanations
    - Just use the data provided to you, do not use your own knowledge
    Context:
    {context}
    """
    )

    llm =ChatOpenAI(
    model="gpt-oss-120b",
    base_url="https://api.sambanova.ai/v1",
    api_key="your_api_key",
    temperature=0
)



    retrieved_docs = retriever.invoke(query)

    context = "\n".join([doc.page_content for doc in retrieved_docs])


    messages = prompt.invoke({
        "context": context,
        "question": query
    })

    response = llm.invoke(messages)

        
    def extract_json(text):
        match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        else:
            raise ValueError("No JSON found")

    json_output = extract_json(response.content)

    print("\n\n\n\n----- FINAL JSON BY LLM -----\n\n\n\n")
    print(json.dumps(json_output, indent=2))

    return json_output



def run_agent(user_query: str):
    
    print("Received query:", user_query)
    
    browser_manager.launch_browser()

    orchestrator(user_query)

    output=final_summarization(final_results,user_query)

    return output
    
