"""Configuration for :class:`~xtr_scheduler.bundle.scheduler_bundle.SchedulerBundle`."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SchedulerConfig"]


@dataclass(frozen=True, slots=True)
class SchedulerConfig:
    """How the scheduler's transports hand over their messages.

    Attributes:
        use_messenger_routing: Hand every scheduled message to routing, so it
            is handled wherever routing sends its type, rather than by the
            worker consuming the schedule. A task naming ``transports`` is
            sent there either way. A transport configured with
            ``?use_messenger_routing=`` on its DSN decides for itself.
    """

    use_messenger_routing: bool = False
