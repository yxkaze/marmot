"""
控制台渠道。

把文本写到一个 TextIO 流（默认 stdout）。仅作为参考实现 + 测试桩。
"""
import sys
from typing import TextIO


class ConsoleChannel:
    """控制台渠道：把消息写到指定输出流。"""

    def __init__(self, output: TextIO | None = None):
        self.output = output if output is not None else sys.stdout

    def write_line(self, text: str) -> None:
        """写入一行文本（自动追加换行符）。"""
        self.output.write(text + "\n")
        self.output.flush()
