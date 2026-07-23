import sys

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from config import MAX_ITER, MODEL, OLLAMA_URL
from prompts import REVIEWER_PROMPT
from state import State
from utils import extract_code, format_run_report, parse_run_result

llm = ChatOllama(model=MODEL, base_url=OLLAMA_URL, temperature=0)

mcp_client = MultiServerMCPClient(
    {
        "code": {
            "command": sys.executable,
            "args": ["code_server.py"],
            "transport": "stdio",
        }
    }
)


def should_continue(state: State) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "reviewer"


def route(state: State) -> str:
    verdict = state["messages"][-1].content.upper()
    if verdict.startswith("APPROVED") or state["iteration"] >= MAX_ITER:
        return END
    return "junior"


_reset_session_tool = None


async def reset_session() -> None:
    """Сбрасывает REPL-сессию run_python, чтобы код нового запроса не выполнялся
    вперемешку с переменными/функциями, оставшимися от предыдущего запроса."""
    if _reset_session_tool is not None:
        await _reset_session_tool.ainvoke({})


async def build_graph():
    global _reset_session_tool
    tools = await mcp_client.get_tools()
    junior_llm = llm.bind_tools(tools)
    run_python = next(tool for tool in tools if tool.name == "run_python")
    _reset_session_tool = next(tool for tool in tools if tool.name == "reset_session")

    async def junior(state: State) -> dict:
        response = await junior_llm.ainvoke(state["messages"])
        return {"messages": [response]}

    async def reviewer(state: State) -> dict:
        answer = state["messages"][-1].content
        code = extract_code(answer)
        print(f"\nКод на ревью (итерация {state['iteration'] + 1}):\n{code}\n")

        raw = await run_python.ainvoke({"code": code})
        report = format_run_report(parse_run_result(raw))

        review = await llm.ainvoke([
            SystemMessage(content=REVIEWER_PROMPT),
            HumanMessage(
                content=(
                    f"Код джуниора:\n\n{answer}\n\n"
                    f"Результат прогона run_python:\n{report}\n\n"
                    "Сделай ревью с учётом результата прогона."
                )
            ),
        ])
        return {
            "messages": [HumanMessage(content=review.content)],
            "iteration": state["iteration"] + 1,
        }

    builder = StateGraph(State)
    builder.add_node("junior", junior)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("reviewer", reviewer)

    builder.add_edge(START, "junior")
    builder.add_conditional_edges(
        "junior", should_continue, {"tools": "tools", "reviewer": "reviewer"}
    )
    builder.add_edge("tools", "junior")
    builder.add_conditional_edges("reviewer", route, {"junior": "junior", END: END})

    return builder.compile()
