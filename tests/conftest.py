"""Shared test fixtures for DictateMe."""

from __future__ import annotations

import pytest

from dictateme.core.config import AppConfig
from dictateme.core.event_bus import EventBus
from dictateme.core.events import Event, EventType


@pytest.fixture
def config() -> AppConfig:
    """Default app configuration for testing."""
    return AppConfig()


@pytest.fixture
def event_bus() -> EventBus:
    """Fresh event bus instance."""
    return EventBus()
