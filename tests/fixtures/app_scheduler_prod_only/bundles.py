"""The application's root bundles."""

from __future__ import annotations

from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_messenger.bundle import MessengerBundle

from xtr_scheduler.bundle import SchedulerBundle

BUNDLES = {
    MessengerBundle: {"all": True},
    EventDispatcherBundle: {"all": True},
    SchedulerBundle: {"all": True},
}
