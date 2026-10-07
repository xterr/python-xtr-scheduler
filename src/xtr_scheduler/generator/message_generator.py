"""Produces a schedule's messages as they fall due."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import Clock

from xtr_scheduler._time import EPOCH, microseconds
from xtr_scheduler.exception import SchedulerLogicError
from xtr_scheduler.trigger.stateful_trigger_interface import StatefulTriggerInterface

from ._trigger_heap import TriggerHeap
from .checkpoint import Checkpoint
from .message_context import MessageContext
from .message_generator_interface import MessageGeneratorInterface

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from datetime import datetime

    from xtr_clock import ClockInterface

    from xtr_scheduler.recurring_message import RecurringMessage
    from xtr_scheduler.schedule import Schedule
    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface
    from xtr_scheduler.trigger.trigger_interface import TriggerInterface

    from .checkpoint_interface import CheckpointInterface

__all__ = ["MessageGenerator"]

_ONE_MICROSECOND: Final = timedelta(microseconds=1)


@final
class MessageGenerator(MessageGeneratorInterface):
    """Turns a schedule into the messages that are due, at least once each.

    Each call to :meth:`get_messages` yields everything due since the last
    one — after downtime, every run that was missed, oldest first, unless the
    schedule asks for only the latest of each. A checkpoint records each
    message once sent, so in the ordinary course a run goes once: not twice by
    this generator, nor again after a restart when the schedule keeps its
    state, nor by another process when the schedule runs under a lock. A run
    recorded after it is handed on, though, means delivery is at least once,
    not exactly once: a crash between sending a message and recording it
    sends that run again on the next pass.

    Between due runs a call returns at once without touching the lock or the
    cache: :attr:`wait_until` says when the next run is due.
    """

    __slots__ = (
        "_checkpoint",
        "_clock",
        "_heap",
        "_heap_initialized",
        "_name",
        "_provider",
        "_schedule",
        "_wait_until",
    )

    def __init__(
        self,
        schedule_provider: ScheduleProviderInterface,
        name: str,
        clock: ClockInterface | None = None,
        checkpoint: CheckpointInterface | None = None,
    ) -> None:
        """Produce the messages of the schedule ``schedule_provider`` hands over, named ``name``.

        ``checkpoint`` left out is a :class:`Checkpoint` named after the
        schedule, using the schedule's lock and state.
        """
        self._provider = schedule_provider
        self._name = name
        self._clock: ClockInterface = clock if clock is not None else Clock()
        self._checkpoint = checkpoint
        self._schedule: Schedule | None = None
        self._heap: TriggerHeap | None = None
        self._heap_initialized = False
        self._wait_until: datetime | None = EPOCH

    @property
    def name(self) -> str:
        """Return the schedule's name."""
        return self._name

    @property
    def schedule(self) -> Schedule:
        """Return the schedule, asking its provider for it the first time."""
        if self._schedule is None:
            self._schedule = self._provider.get_schedule()
        return self._schedule

    @property
    @override
    def wait_until(self) -> datetime | None:
        """Return when the next run is due; ``None`` once nothing will ever be due again."""
        return self._wait_until

    @override
    async def get_messages(self) -> AsyncGenerator[tuple[MessageContext, object]]:
        """Yield every message due by now, oldest run first.

        Each message is recorded as sent once the one after it is asked for —
        or when iteration stops, however it stops — so close the iterator
        (``async with contextlib.aclosing(...)``) rather than abandon it.

        Raises:
            SchedulerLogicError: If a trigger answers a date that is not
                strictly after the one it was asked about.
        """
        checkpoint = self._checkpoint_of_schedule()
        self._restart_if_changed()
        if self._wait_until is None:
            return
        now = self._clock.now()
        # Every comparison is between instants: two dates on one zone compare by
        # their wall clock, and the hour a clock goes back happens twice on it.
        now_at = microseconds(now)
        if microseconds(self._wait_until) > now_at or not await checkpoint.acquire(now):
            return

        heap: TriggerHeap | None = None
        try:
            last_time = checkpoint.time()
            last_index = checkpoint.index()
            heap = self._heap_for(last_time, checkpoint.from_(), last_index)
            last_at = microseconds(last_time)
            while heap and microseconds(heap.top()[0]) <= now_at:
                time, index, recurring_message = heap.extract()
                time_at = microseconds(time)
                # Already sent: before what was last sent, or at that time but not after it.
                send = time_at > last_at or (time_at == last_at and index > last_index)
                time = time if time_at >= last_at else last_time
                trigger = recurring_message.get_trigger()
                entry = (time, index, recurring_message)
                if send and self._reschedule_to_latest(heap, entry, now_at):
                    continue
                next_time = self._next_time(trigger, time)
                if next_time is not None:
                    heap.insert(next_time, index, recurring_message)
                if not send:
                    continue
                context = MessageContext(self._name, recurring_message.id, trigger, time, next_time)
                # Record the run only once at least one of its messages was
                # handed on: a provider that raises or is cancelled before
                # yielding leaves the checkpoint untouched, so the next pass
                # runs it again — delivery is at least once, never zero.
                started = False
                try:
                    async for message in recurring_message.get_messages(context):
                        started = True
                        yield context, message
                finally:
                    if started:
                        await checkpoint.save(time, index)
        finally:
            # A run that ended — iteration stopped early, or building the plan
            # failed — still hands the lock back. With a plan, say what is due
            # next and keep the lock until then; a failure before one leaves the
            # next due time as it was, to try again, and hands the lock back now.
            next_time = heap.top()[0] if heap else None
            if heap is not None:
                self._wait_until = next_time
            await checkpoint.release(now, next_time)

    @override
    async def close(self) -> None:
        """Hand back the schedule's lock, if held — the next process need not wait for it."""
        if self._checkpoint is not None:
            await self._checkpoint.close()

    def _restart_if_changed(self) -> None:
        """Drop the plan when the schedule's messages changed, so it is rebuilt from them."""
        if self._schedule is not None and self._schedule.should_restart:
            self._heap = None
            self._wait_until = EPOCH
            self._schedule.set_restart(False)

    @staticmethod
    def _latest_due(trigger: TriggerInterface, time: datetime, now_at: int) -> datetime:
        """Return the latest run of ``trigger`` due by ``now_at``, counting from the due ``time``.

        ``time`` itself when no later run is due yet. A trigger that does not
        move forward stops the walk; :meth:`_next_time` reports it.
        """
        latest = time
        candidate = trigger.get_next_run_date(time)
        while candidate is not None and microseconds(latest) < microseconds(candidate) <= now_at:
            latest = candidate
            candidate = trigger.get_next_run_date(candidate)
        return latest

    @staticmethod
    def _next_time(trigger: TriggerInterface, time: datetime) -> datetime | None:
        """Return when ``trigger`` fires after ``time``.

        Raises:
            SchedulerLogicError: If the trigger answers a date not strictly
                after the one it was asked about.
        """
        previous_time = time
        next_time = trigger.get_next_run_date(time)
        if next_time is not None and microseconds(next_time) <= microseconds(previous_time):
            raise SchedulerLogicError(
                f'The "{trigger}" trigger does not move the run date forward. Its '
                '"get_next_run_date()" method must return a date strictly after the given one.'
            )
        return next_time

    def _heap_for(self, time: datetime, start_time: datetime, last_index: int) -> TriggerHeap:
        """Return the plan of what runs next, rebuilding it when it is older than ``time``."""
        if self._heap is not None and microseconds(self._heap.time) <= microseconds(time):
            return self._heap
        heap = TriggerHeap(time)
        # The first plan of a process resuming a batch it half sent (last_index
        # at or past 0) asks the triggers from one microsecond earlier: triggers
        # answer strictly after, so the runs due exactly at ``time`` come back,
        # and the checks in get_messages skip the part already sent. Later
        # rebuilds follow a whole batch, so asking earlier would resend it.
        probe = time - _ONE_MICROSECOND if not self._heap_initialized and last_index >= 0 else time
        self._heap_initialized = True
        for index, recurring_message in enumerate(self.schedule.recurring_messages):
            trigger = recurring_message.get_trigger()
            if isinstance(trigger, StatefulTriggerInterface):
                trigger.continue_(start_time)
            next_time = trigger.get_next_run_date(probe)
            if next_time is not None:
                heap.insert(next_time, index, recurring_message)
        self._heap = heap
        return heap

    def _reschedule_to_latest(
        self,
        heap: TriggerHeap,
        entry: tuple[datetime, int, RecurringMessage],
        now_at: int,
    ) -> bool:
        """Skip a missed run to its latest due instant when the schedule asks only for that.

        Returns ``True`` when the run was put back on the heap at a later
        instant — sent when its turn comes, so what is recorded as sent never
        moves backwards — and the caller should move on.
        """
        if not self.schedule.should_process_only_last_missed_run():
            return False
        time, index, recurring_message = entry
        latest = self._latest_due(recurring_message.get_trigger(), time, now_at)
        if latest is time:
            return False
        heap.insert(latest, index, recurring_message)
        return True

    def _checkpoint_of_schedule(self) -> CheckpointInterface:
        if self._checkpoint is None:
            schedule = self.schedule
            self._checkpoint = Checkpoint(
                f"scheduler_checkpoint_{self._name}", schedule.get_lock(), schedule.get_state()
            )
        return self._checkpoint
