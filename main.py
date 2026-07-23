import asyncio

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

from config import MAX_ITER, MAX_RETRIES, MODEL, RETRY_DELAY
from graph import build_graph, reset_session
from prompts import JUNIOR_PROMPT
from utils import save_graph_png, trim_context_if_needed


async def main() -> None:
    graph = await build_graph()
    save_graph_png(graph)

    print(f"Джуниор + Ревьюер с исполнением кода через MCP, петля до {MAX_ITER} кругов ({MODEL}). Напиши 'exit' для выхода.\n")
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

        # Каждый запрос - независимая задача с чистого листа: не тащим в контекст
        # код и вердикты из предыдущих запросов, чтобы модель их не путала и не переиспользовала.
        messages: list[AnyMessage] = [
            SystemMessage(content=JUNIOR_PROMPT),
            HumanMessage(content=user_input),
        ]
        await reset_session()

        for attempt in range(MAX_RETRIES):
            try:
                result = await graph.ainvoke({"messages": messages, "iteration": 0})
                break
            except Exception as e:
                print(f"Ошибка (попытка {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt + 1 < MAX_RETRIES:
                    delay = RETRY_DELAY * 2 ** attempt
                    print(f"Повтор через {delay} с...")
                    await asyncio.sleep(delay)
        else:
            continue

        final_messages = trim_context_if_needed(result["messages"])

        print(f"\nВердикт ревьюера (после {result['iteration']} ревью):\n{final_messages[-1].content}\n")


if __name__ == "__main__":
    asyncio.run(main())
