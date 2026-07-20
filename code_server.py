import subprocess
import sys
import tempfile
from pathlib import Path

from fastmcp import FastMCP

from config import EXEC_TIMEOUT

mcp = FastMCP("code-runner")


@mcp.tool
def run_python(code: str) -> dict:
    """Запускает переданный код на Python в отдельном процессе и возвращает результат.

    Используй этот инструмент, чтобы реально проверить работоспособность кода:
    прогнать примеры, увидеть вывод или поймать ошибку выполнения.
    В поле `code` передавай законченный скрипт, который сам печатает результат через print().

    Возвращает словарь с полями:
      ok      - True, если код завершился без ошибок (код возврата 0);
      stdout  - то, что код напечатал в стандартный вывод;
      stderr  - текст ошибки или предупреждений, если они были;
      returncode - код возврата процесса.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "snippet.py"
        script.write_text(code, encoding="utf-8")

        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "stdout": "",
                "stderr": f"Превышен лимит времени выполнения ({EXEC_TIMEOUT} с).",
                "returncode": -1,
            }

    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
