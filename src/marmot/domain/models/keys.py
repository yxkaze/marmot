"""
键生成工具函数。

提供去重键、标签规范化等纯函数，无 I/O，无状态。
"""

from typing import Any, Iterable


def build_dedup_key(rule_name: str, labels: dict[str, Any] | None = None) -> str:
    """根据规则名和标签生成确定性的去重键。
    
    去重键用于标识同一个告警的不同实例。相同规则名和相同标签组合
    产生相同的去重键，从而实现告警去重。
    
    参数:
        rule_name: 规则名称
        labels: 标签字典（可选）
        
    返回:
        去重键字符串
        
    示例:
        build_dedup_key("cpu_usage", {"host": "prod-1", "region": "us-east"})
        # 返回 "cpu_usage:host=prod-1,region=us-east"
        
        build_dedup_key("heartbeat")
        # 返回 "heartbeat"
        
        build_dedup_key("cpu_usage", {"b": "2", "a": "1"})
        # 返回 "cpu_usage:a=1,b=2" (标签按 key 排序)
    """
    if not labels:
        return rule_name
    
    parts = [f"{k}={v}" for k, v in sorted(labels.items())]
    return f"{rule_name}:{','.join(parts)}"


def normalize_notify(v: str | Iterable[str] | None) -> list[str]:
    """将通知目标规范化为字符串列表。
    
    支持多种输入格式:
        - None: 返回空列表
        - 字符串: 按逗号分隔后返回列表
        - 可迭代对象: 转换为字符串列表
        
    参数:
        v: 通知目标，可以是字符串、列表或 None
        
    返回:
        规范化后的字符串列表
        
    示例:
        normalize_notify(None)                    # 返回 []
        normalize_notify("dingtalk")              # 返回 ["dingtalk"]
        normalize_notify("dingtalk, email, sms")  # 返回 ["dingtalk", "email", "sms"]
        normalize_notify(["dingtalk", "email"])   # 返回 ["dingtalk", "email"]
    """
    if not v:
        return []
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    return [str(x).strip() for x in v if str(x).strip()]
