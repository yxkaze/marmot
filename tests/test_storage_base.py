"""
测试存储层 Protocol 定义。
"""
from marmot.storage.base import AlertEventStorage, RunRecordStorage, NotificationStorage


def test_all_are_protocol():
    """三个 Storage 都应该是 Protocol。"""
    from typing import Protocol
    assert issubclass(AlertEventStorage, Protocol)
    assert issubclass(RunRecordStorage, Protocol)
    assert issubclass(NotificationStorage, Protocol)


def test_alert_event_storage_methods():
    """AlertEventStorage 应该有标准 CRUD 方法。"""
    assert hasattr(AlertEventStorage, 'create_alert_event')
    assert hasattr(AlertEventStorage, 'update_alert_event')
    assert hasattr(AlertEventStorage, 'get_alert')
    assert hasattr(AlertEventStorage, 'get_active_alert')
    assert hasattr(AlertEventStorage, 'list_active_alerts')
    assert hasattr(AlertEventStorage, 'list_alert_history')


def test_run_record_storage_methods():
    """RunRecordStorage 应该有标准 CRUD 方法。"""
    assert hasattr(RunRecordStorage, 'create_run')
    assert hasattr(RunRecordStorage, 'update_run')
    assert hasattr(RunRecordStorage, 'get_run')
    assert hasattr(RunRecordStorage, 'get_latest_run')
    assert hasattr(RunRecordStorage, 'list_runs')


def test_notification_storage_methods():
    """NotificationStorage 应该有标准 CRUD 方法。"""
    assert hasattr(NotificationStorage, 'record_notification')
    assert hasattr(NotificationStorage, 'list_notifications')
