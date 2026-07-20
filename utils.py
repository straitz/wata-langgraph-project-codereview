import json
import re

from langchain_core.messages import AnyMessage, SystemMessage, ToolMessage

from config import MAX_MESSAGES

CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    blocks = CODE_BLOCK.findall(text)
    return blocks[-1].strip() if blocks else text.strip()


def parse_run_result(raw) -> dict:
    # MCP-инструмент возвращает список content-блоков - собираем из них текст.
    if isinstance(raw, list):
        raw = "".join(b.get("text", "") for b in raw if isinstance(b, dict))
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {"ok": False, "stdout": "", "stderr": str(raw), "returncode": -1}


def format_run_report(run: dict) -> str:
    status = "успешно" if run["ok"] else "с ошибкой"
    return (
        f"Статус: {status} (returncode={run['returncode']})\n"
        f"stdout:\n{run['stdout'] or '(пусто)'}\n"
        f"stderr:\n{run['stderr'] or '(пусто)'}"
    )


def trim_context_if_needed(messages: list[AnyMessage]) -> list[AnyMessage]:
    if len(messages) <= MAX_MESSAGES:
        return messages

    system_msgs = [msg for msg in messages if isinstance(msg, SystemMessage)]
    dialog_msgs = [msg for msg in messages if not isinstance(msg, SystemMessage)]

    keep = max(MAX_MESSAGES - len(system_msgs), 0)
    recent_msgs = dialog_msgs[-keep:] if keep else []

    # Не даём окну начаться с "осиротевшего" результата инструмента без вызова.
    while recent_msgs and isinstance(recent_msgs[0], ToolMessage):
        recent_msgs = recent_msgs[1:]

    return system_msgs + recent_msgs


def save_graph_png(graph, path: str = "graph.png") -> None:
    try:
        png = graph.get_graph().draw_mermaid_png()
        with open(path, "wb") as f:
            f.write(png)
        print(f"Схема графа сохранена в {path}")
    except Exception as e:
        print(f"Не удалось сохранить схему графа: {e}")
