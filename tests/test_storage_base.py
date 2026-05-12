"""
测试 Storage Protocol 定义。
"""
import pytest
from marmot.storage.base import Storage


def test_storage_is_protocol():
    """Storage 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Storage, Protocol)


def test_storage_has_required_methods():
    """Storage 应该有必需的方法签名。"""
    # 这是一个编译时检查，运行时只需确认 Protocol 存在
    assert hasattr(Storage, 'get_or_create_alert_event')
    assert hasattr(Storage, 'update_alert_event')
    assert hasattr(Storage, 'list_active_alerts')
    assert hasattr(Storage, 'list_alert_history')
    assert hasattr(Storage, 'create_run_record')
    assert hasattr(Storage, 'list_recent_runs')
    assert hasattr(Storage, 'create_notification')
    assert hasattr(Storage, 'list_notifications')
