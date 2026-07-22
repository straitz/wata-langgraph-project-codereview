import ast
import builtins
import functools
import io
import threading
import traceback

from fastmcp import FastMCP

from config import EXEC_TIMEOUT

mcp = FastMCP("code-runner")

# Одна живая сессия на всё время работы сервера: переменные, импорты и функции
# сохраняются между вызовами run_python, как в интерактивном терминале / ячейках ноутбука.
_session: dict = {"__name__": "__main__"}
_session_lock = threading.Lock()


def _fresh_session() -> dict:
    return {"__name__": "__main__"}


def _run_in_session(code: str, out: io.StringIO, err: io.StringIO, box: dict) -> None:
    """Выполняет код в общем namespace. Значение последнего выражения печатается,
    как это делает REPL: `x + 1` в конце ячейки выведет результат без print().

    Вывод исполняемого кода перехватываем, подменяя print именно внутри сессии
    (а не глобальный sys.stdout) - иначе зависший по таймауту поток сломал бы
    stdio-транспорт MCP-сервера, который тоже пишет в stdout.
    """
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        traceback.print_exc(file=err)
        box["ok"] = False
        return

    # Если последний оператор - "голое" выражение, вычислим его отдельно и напечатаем.
    last_expr = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last_expr = ast.Expression(tree.body.pop().value)

    _session["print"] = functools.partial(builtins.print, file=out)
    try:
        exec(compile(tree, "<session>", "exec"), _session)
        if last_expr is not None:
            value = eval(compile(last_expr, "<session>", "eval"), _session)
            if value is not None:
                builtins.print(repr(value), file=out)
        box["ok"] = True
    except Exception:
        traceback.print_exc(file=err)
        box["ok"] = False


@mcp.tool
def run_python(code: str) -> dict:
    """Выполняет код Python в постоянной интерактивной сессии (как терминал/ноутбук).

    Состояние СОХРАНЯЕТСЯ между вызовами: переменные, импорты и функции, объявленные
    в прошлый раз, остаются доступны. Можно писать код по шагам, как человек за REPL:
    сначала объявить данные, потом в следующем вызове их использовать.
    Значение последнего выражения печатается автоматически - print() нужен только
    для промежуточного вывода.

    Возвращает словарь с полями:
      ok         - True, если код выполнился без исключений;
      stdout     - напечатанный вывод и значение последнего выражения;
      stderr     - трейсбек исключения, если оно возникло;
      returncode - 0 при успехе, 1 при исключении, -1 при таймауте.
    """
    out, err = io.StringIO(), io.StringIO()
    box: dict = {"ok": False}

    with _session_lock:
        worker = threading.Thread(
            target=_run_in_session, args=(code, out, err, box), daemon=True
        )
        worker.start()
        worker.join(timeout=EXEC_TIMEOUT)

        if worker.is_alive():
            # Поток нельзя безопасно убить, поэтому сообщаем о таймауте; он продолжит
            # крутиться в фоне. Вывод идёт в наш буфер, а не в stdout сервера.
            return {
                "ok": False,
                "stdout": out.getvalue(),
                "stderr": f"Превышен лимит времени выполнения ({EXEC_TIMEOUT} с).",
                "returncode": -1,
            }

    return {
        "ok": box["ok"],
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "returncode": 0 if box["ok"] else 1,
    }


@mcp.tool
def reset_session() -> dict:
    """Сбрасывает сессию Python - как перезапуск ядра: все переменные, импорты и
    функции забываются, следующий run_python начинается с чистого namespace."""
    with _session_lock:
        _session.clear()
        _session.update(_fresh_session())
    return {"ok": True, "stdout": "Сессия сброшена.", "stderr": "", "returncode": 0}


if __name__ == "__main__":
    mcp.run(transport="stdio")
