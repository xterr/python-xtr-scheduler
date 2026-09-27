"""A set of recurring messages, and how they are run."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher

from .event import FailureEvent, PostRunEvent, PreRunEvent
from .exception import SchedulerLogicError
from .schedule_provider_interface import ScheduleProviderInterface

if TYPE_CHECKING:
    from xtr_cache_contracts import CacheInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface, Listener
    from xtr_lock import LockInterface

    from .recurring_message import RecurringMessage

__all__ = ["Schedule"]


@final
class Schedule(ScheduleProviderInterface):
    """The recurring messages one scheduler transport runs, and how it runs them.

    Without a lock, every process running the schedule sends every message;
    give it one — :meth:`lock` — and only the process holding it does. Without
    saved state, a restarted process starts over from the time it started;
    give it a cache — :meth:`stateful` — and it picks up where the last one
    stopped, sending what was missed in between.

    Changing the set of messages while the schedule runs is safe: the next
    time it is asked for messages it rebuilds its plan, and what already ran
    is not sent again.
    """

    __slots__ = ("_listeners", "_lock", "_messages", "_only_last_missed", "_restart", "_state")

    def __init__(self, *messages: RecurringMessage) -> None:
        """Start with ``messages``.

        Raises:
            SchedulerLogicError: If two of them are the same recurring message.
        """
        self._messages: dict[str, RecurringMessage] = {}
        self._lock: LockInterface | None = None
        self._state: CacheInterface | None = None
        self._restart = False
        self._only_last_missed = False
        self._listeners: EventDispatcher | None = None
        _ = self.add(*messages)

    def __copy__(self) -> Schedule:
        """Return a schedule with the same lock, state and listeners, and its own messages.

        What ``copy.copy`` gives: a starting point for a variation of this
        schedule — adding to the copy, or listening on it, leaves this one as
        it is.
        """
        clone = Schedule(*self._messages.values())
        clone._lock, clone._state = self._lock, self._state
        clone._only_last_missed = self._only_last_missed
        if self._listeners is not None:
            for name, listeners in self._listeners.get_listeners().items():
                for listener in listeners:
                    priority = self._listeners.get_listener_priority(name, listener) or 0
                    clone._dispatcher().add_listener(name, listener, priority)
        return clone

    def add(self, *messages: RecurringMessage) -> Self:
        """Add ``messages``.

        Raises:
            SchedulerLogicError: If one is already in the schedule.
        """
        for message in messages:
            if message.id in self._messages:
                raise SchedulerLogicError("Duplicated schedule message.")
            self._messages[message.id] = message
        self._restart = self._restart or bool(messages)
        return self

    def remove(self, message: RecurringMessage) -> Self:
        """Remove ``message``, if it is in the schedule."""
        return self.remove_by_id(message.id)

    def remove_by_id(self, id_: str) -> Self:
        """Remove the recurring message identified by ``id_``, if it is in the schedule."""
        _ = self._messages.pop(id_, None)
        self._restart = True
        return self

    def clear(self) -> Self:
        """Remove every recurring message."""
        self._messages.clear()
        self._restart = True
        return self

    def lock(self, lock: LockInterface) -> Self:
        """Run only in the process that holds ``lock``, and keep it held between runs."""
        self._lock = lock
        return self

    def get_lock(self) -> LockInterface | None:
        """Return the lock the schedule runs under, if any."""
        return self._lock

    def stateful(self, state: CacheInterface) -> Self:
        """Keep what already ran in ``state``, so a restart resumes rather than starts over."""
        self._state = state
        return self

    def get_state(self) -> CacheInterface | None:
        """Return where the schedule keeps what already ran, if anywhere."""
        return self._state

    def process_only_last_missed_run(self, only_last_missed: bool) -> Self:
        """After downtime, send only the latest missed run of each message, not every one."""
        self._only_last_missed = only_last_missed
        return self

    def should_process_only_last_missed_run(self) -> bool:
        """Tell whether only the latest missed run of each message is sent after downtime."""
        return self._only_last_missed

    @property
    def recurring_messages(self) -> tuple[RecurringMessage, ...]:
        """Return the recurring messages, in the order they were added."""
        return tuple(self._messages.values())

    @override
    def get_schedule(self) -> Self:
        return self

    def before(self, listener: Listener, priority: int = 0) -> Self:
        """Call ``listener`` with a :class:`PreRunEvent` before each of this schedule's runs."""
        self._dispatcher().add_listener(PreRunEvent, listener, priority)
        return self

    def after(self, listener: Listener, priority: int = 0) -> Self:
        """Call ``listener`` with a :class:`PostRunEvent` after each of this schedule's runs."""
        self._dispatcher().add_listener(PostRunEvent, listener, priority)
        return self

    def on_failure(self, listener: Listener, priority: int = 0) -> Self:
        """Call ``listener`` with a :class:`FailureEvent` when one of this schedule's runs fails."""
        self._dispatcher().add_listener(FailureEvent, listener, priority)
        return self

    @property
    def event_dispatcher(self) -> EventDispatcherInterface | None:
        """Return the dispatcher of this schedule's own listeners, if it has any."""
        return self._listeners

    @property
    def should_restart(self) -> bool:
        """Tell whether the set of messages changed since the plan was last built."""
        return self._restart

    def set_restart(self, restart: bool) -> None:
        """Record whether the plan must be rebuilt — the generator clears it once it has."""
        self._restart = restart

    def _dispatcher(self) -> EventDispatcher:
        if self._listeners is None:
            self._listeners = EventDispatcher()
        return self._listeners
