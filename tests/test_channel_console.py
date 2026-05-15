"""ConsoleChannel 测试。"""
import io

from marmot.channels.console import ConsoleChannel


def test_write_line_appends_newline():
    """write_line 应自动追加换行符。"""
    buf = io.StringIO()
    ch = ConsoleChannel(output=buf)
    ch.write_line("hello")
    assert buf.getvalue() == "hello\n"


def test_write_line_multiple():
    """多次写入应顺序累加。"""
    buf = io.StringIO()
    ch = ConsoleChannel(output=buf)
    ch.write_line("a")
    ch.write_line("b")
    assert buf.getvalue() == "a\nb\n"


def test_default_output_is_stdout():
    """未传 output 时默认绑定 sys.stdout。"""
    import sys
    ch = ConsoleChannel()
    assert ch.output is sys.stdout
