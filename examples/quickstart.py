"""
快速开始示例。

演示如何使用 Marmot 创建阈值规则并触发告警。
"""
from marmot import (
    configure,
    register_threshold_rule,
    register_sink,
    report,
    shutdown,
    ThresholdRule,
    ThresholdLevel,
    console_sink,
    Severity,
)


def main():
    print("=== Marmot 快速开始 ===\n")
    
    # 1. 配置 Marmot（内存存储）
    print("1. 配置 Marmot")
    app = configure(storage="memory")
    
    # 2. 注册 Sink
    print("2. 注册控制台 Sink")
    register_sink("console", console_sink)
    
    # 3. 注册阈值规则
    print("3. 注册 CPU 使用率告警规则")
    register_threshold_rule(ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
        ],
        consecutive_count=3,
        silence_seconds=0,
        notify_targets=["console"],
    ))
    
    # 4. 模拟上报数据
    print("\n4. 模拟上报数据...")
    for i in [70, 85, 86, 87, 92, 75, 70]:
        print(f"   CPU {i}%")
        report("cpu_high", float(i), {"host": "server1"})
    
    # 5. 检查活跃告警
    print("\n5. 检查活跃告警:")
    alerts = app.list_active_alerts()
    print(f"   活跃告警数量: {len(alerts)}")
    for alert in alerts:
        print(f"   - {alert.rule_name}: {alert.state}")
    
    # 6. 关闭
    print("\n6. 关闭 Marmot")
    shutdown()
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()

