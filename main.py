import os
import time
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MAX_ITER = 3
MAX_RETRIES = 3
RETRY_DELAY = 1  # базовая задержка в секундах, растёт: 1, 2, 4...
MAX_MESSAGES = 16

JUNIOR_PROMPT = (
    "Ты - ИИ-ассистент программист. Пиши простой, понятный код по запросу пользователя. " 
    "Показывай код в markdown-блоке и коротко поясняй, что он делает. "
    "Если тебе дают замечания ревьюера - исправь код с их учётом. Отвечай на русском языке."
)

REVIEWER_PROMPT = (
    "Ты - старший разработчик и делаешь ревью кода джуниора. "
    "Если код корректен и готов - начни ответ строго со слова APPROVED, затем короткий комментарий. "
    "Если нужны правки - начни ответ строго со слова REVISE, затем перечисли конкретные замечания. "
    "Отвечай на русском языке."
)

llm = ChatOllama(model=MODEL, base_url=OLLAMA_URL, temperature=0)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    iteration: int


def junior(state: State) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


def reviewer(state: State) -> dict:
    code = state["messages"][-1].content
    review = llm.invoke([
        SystemMessage(content=REVIEWER_PROMPT),
        HumanMessage(content=f"Сделай ревью этого кода:\n\n{code}"),
    ])
    return {
        "messages": [HumanMessage(content=review.content)],
        "iteration": state["iteration"] + 1,
    }


def trim_context_if_needed(messages: list[AnyMessage]):
    if len(messages) <= MAX_MESSAGES:
        return messages

    system_msgs = [msg for msg in messages if isinstance(msg, SystemMessage)]
    dialog_msgs = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    keep = max(MAX_MESSAGES - len(system_msgs), 0)
    recent_msgs = dialog_msgs[-keep:] if keep else []
    return system_msgs + recent_msgs


def route(state: State) -> str:
    verdict = state["messages"][-1].content.upper()
    if verdict.startswith("APPROVED") or state["iteration"] >= MAX_ITER:
        return END
    return "junior"


def build_graph():
    builder = StateGraph(State)
    builder.add_node("junior", junior)
    builder.add_node("reviewer", reviewer)
    builder.add_edge(START, "junior")
    builder.add_edge("junior", "reviewer")
    builder.add_conditional_edges("reviewer", route, {"junior": "junior", END: END})
    return builder.compile()


def save_graph_png(graph, path="graph.png"):
    try:
        png = graph.get_graph().draw_mermaid_png()
        with open(path, "wb") as f:
            f.write(png)
        print(f"Схема графа сохранена в {path}")
    except Exception as e:
        print(f"Не удалось сохранить схему графа: {e}")


def main() -> None:
    graph = build_graph()
    save_graph_png(graph)

    history: list[AnyMessage] = [SystemMessage(content=JUNIOR_PROMPT)]

    print(f"Джуниор + Ревьюер, петля до {MAX_ITER} кругов ({MODEL}). Напиши 'exit' для выхода.\n")
    while True:
        try:
            user_input = input("Ты: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user_input.lower() in {"exit", "quit", "выход"}:
            break
        if not user_input:
            continue

        history.append(HumanMessage(content=user_input))

        for attempt in range(MAX_RETRIES):
            try:
                result = graph.invoke({"messages": history, "iteration": 0})
                break
            except Exception as e:
                print(f"Ошибка (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt + 1 < MAX_RETRIES:
                    delay = RETRY_DELAY * 2 ** attempt
                    print(f"Повтор через {delay} с...")
                    time.sleep(delay)
        else:
            history.pop()
            continue

        history = trim_context_if_needed(result["messages"])

        print(f"\nФинальный код (после {result['iteration']} ревью):\n{history[-2].content}\n")
        print(f"Вердикт ревьюера:\n{history[-1].content}\n")


if __name__ == "__main__":
    main()
