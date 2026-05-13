"""
测试 Storage Protocol 定义。
"""
from marmot.storage.base import Storage


def test_storage_is_protocol():
    """Storage 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Storage, Protocol)


def test_storage_has_required_methods():
    """Storage 应该有标准 CRUD 方法签名。"""
    # AlertEvent
    assert hasattr(Storage, 'create_alert_event')
    assert hasattr(Storage, 'update_alert_event')
    assert hasattr(Storage, 'get_alert')
    assert hasattr(Storage, 'get_active_alert')
    assert hasattr(Storage, 'list_active_alerts')
    assert hasattr(Storage, 'list_alert_history')
    # RunRecord
    assert hasattr(Storage, 'create_run')
    assert hasattr(Storage, 'update_run')
    assert hasattr(Storage, 'get_run')
    assert hasattr(Storage, 'get_latest_run')
    assert hasattr(Storage, 'list_runs')
    # Notification
    assert hasattr(Storage, 'record_notification')
    assert hasattr(Storage, 'list_notifications')
