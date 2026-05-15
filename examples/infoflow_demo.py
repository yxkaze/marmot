"""
如流（InfoFlow）告警示例。

演示：
    1. 用 ``InfoFlowChannel`` 直接发送原生消息（验证 webhook 可用）；
    2. 把 channel 包装成 sink 注册到 Marmot，由 dispatcher 触发；
    3. sink 内部决定渲染格式，并写回 ``notification.message`` 用于审计。

运行前请将 ``WEBHOOK_URL`` / ``GROUP_ID`` 替换为你机器人的真实值。
"""
from __future__ import annotations

from marmot import (
    Severity,
    ThresholdLevel,
    ThresholdRule,
    configure,
    register_sink,
    register_threshold_rule,
    report,
    shutdown,
)
from marmot.channels import InfoFlowChannel
from marmot.domain.models.events import Notification


# ── 用户填入 ────────────────────────────────────────────
WEBHOOK_URL = "https://infoflow.baidu.com/api/im/group/chatbot/send?token=REPLACE_ME"
GROUP_ID = 0  # 群 id，替换为你的真实值
AT_USER_IDS: list[int] = []   # 需要 @ 的用户 id 列表，留空表示不 @


def make_infoflow_sink(channel: InfoFlowChannel):
    """把 InfoFlowChannel 包成一个 sink（Callable[[Notification], bool]）。

    用户在这里完全掌控：
        - 发什么类型（这里用 markdown，含状态、严重度、标签）
        - 是否 @ 人（FIRING 状态 + ERROR 及以上才 @）
        - 写回 notification.message，让 dispatcher 持久化实际发送内容
    """
    def sink(n: Notification) -> bool:
        labels = " ".join(f"`{k}={v}`" for k, v in n.labels.items())
        state = n.state.value if n.state else "UNKNOWN"
        severity = n.severity.value if n.severity else "INFO"
        ts = n.sent_at.strftime("%Y-%m-%d %H:%M:%S")

        rendered = (
            f"### [{state.upper()}] {n.rule_name}\n"
            f"- 严重度：**{severity}**\n"
            f"- 标签：{labels or '(无)'}\n"
            f"- 时间：{ts}\n"
            f"- 详情：{n.message}\n"
        )

        try:
            should_at = (
                state == "firing"
                and n.severity is not None
                and n.severity in (Severity.ERROR, Severity.CRITICAL)
                and AT_USER_IDS
            )
            if should_at:
                # AT 不能与 MD 混用，退化成 TEXT
                channel.send_text(_md_to_text(rendered), at_user_ids=AT_USER_IDS)
            else:
                channel.send_markdown(rendered)
        except Exception as e:  # noqa: BLE001 — sink 内吞掉异常，让 dispatcher 标记 FAILED
            print(f"[infoflow_sink] send failed: {e}")
            return False

        # ★ 写回，让 dispatcher 把"实际发送内容"持久化
        n.message = rendered
        return True

    return sink


def _md_to_text(md: str) -> str:
    """简单去掉 markdown 标记，给 TEXT 模式用。"""
    out = []
    for line in md.splitlines():
        line = line.lstrip("# ").replace("**", "").replace("`", "")
        out.append(line)
    return "\n".join(out)


def main() -> None:
    print("=== Marmot × InfoFlow 示例 ===\n")

    channel = InfoFlowChannel(webhook_url=WEBHOOK_URL, to_ids=[GROUP_ID])

    # 1. 直接用 channel 发一条，确认 webhook 通
    print("1. 直接用 channel.send_text 发送 ping")
    try:
        channel.send_text("Marmot 接入测试：hello from InfoFlowChannel")
    except Exception as e:  # noqa: BLE001
        print(f"   webhook 不可用：{e}")
        print("   （示例继续，但实际不会发出消息）")

    # 2. 走完整告警链路
    print("\n2. 配置 Marmot + 注册 sink")
    configure(storage="memory")
    register_sink("infoflow", make_infoflow_sink(channel))

    register_threshold_rule(ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
        ],
        consecutive_count=2,
        silence_seconds=0,
        notify_targets=["infoflow"],
    ))

    print("3. 模拟上报数据（先升后降，触发 firing → resolved）")
    for v in [70, 85, 92, 95, 60, 50]:
        print(f"   CPU {v}%")
        report("cpu_high", float(v), {"host": "server1", "env": "prod"})

    print("\n4. 关闭")
    shutdown()
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
