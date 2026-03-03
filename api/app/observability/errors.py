import traceback
from typing import Any


def format_exception(ex: BaseException, max_tb_lines: int = 12) -> dict[str, Any]:
    tb = traceback.format_exception(type(ex), ex, ex.__traceback__)
    tb_text = "".join(tb).splitlines()
    if len(tb_text) > max_tb_lines:
        tb_text = tb_text[:max_tb_lines] + ["... (truncated)"]
    return {
        "type": type(ex).__name__,
        "message": str(ex),
        "traceback": tb_text,
    }