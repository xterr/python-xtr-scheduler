"""Recurring messages on xtr-messenger.

A :class:`Schedule` holds :class:`RecurringMessage` s — a message and when to
send it, on a cron expression or every so often. A scheduler transport
(``schedule://<name>``) turns the schedule into messages as they fall due, and
a messenger worker consumes it like any other transport: each message is
handled there, or sent on to where routing puts it.
"""

from __future__ import annotations

from .recurring_message import RecurringMessage
from .schedule import Schedule
from .schedule_provider_interface import ScheduleProviderInterface

__all__ = ["RecurringMessage", "Schedule", "ScheduleProviderInterface"]
