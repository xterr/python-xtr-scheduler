"""Recurring messages on xtr-messenger.

A :class:`Schedule` holds :class:`RecurringMessage` s — a message and when to
send it, on a cron expression or every so often. A scheduler transport
(``schedule://<name>``) turns the schedule into messages as they fall due, and
a messenger worker consumes it like any other transport: each message is
handled there, or sent on to where routing puts it.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .recurring_message import RecurringMessage
from .schedule import Schedule
from .schedule_provider_interface import ScheduleProviderInterface

__all__ = ["RecurringMessage", "Schedule", "ScheduleProviderInterface", "__version__"]

try:
    __version__ = version("xtr-scheduler")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read; having no
    # version is better than refusing to import.
    __version__ = "0+unknown"
