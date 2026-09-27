"""The recurring messages of a schedule, earliest next run first."""

from __future__ import annotations

from tests.support.dates import at
from tests.support.messages import Plain
from xtr_scheduler import RecurringMessage
from xtr_scheduler.generator._trigger_heap import TriggerHeap


def test_entries_come_out_by_time_then_by_position() -> None:
    heap = TriggerHeap(at("2026-01-01T00:00:00+00:00"))
    first, second = RecurringMessage.every(60, Plain(1)), RecurringMessage.every(60, Plain(2))
    heap.insert(at("2026-01-01T00:02:00+00:00"), 0, first)
    heap.insert(at("2026-01-01T00:01:00+00:00"), 1, second)
    heap.insert(at("2026-01-01T00:01:00+00:00"), 0, first)

    order = [heap.extract()[:2] for _ in range(3)]

    assert order == [
        (at("2026-01-01T00:01:00+00:00"), 0),
        (at("2026-01-01T00:01:00+00:00"), 1),
        (at("2026-01-01T00:02:00+00:00"), 0),
    ]
    assert not heap


def test_top_shows_the_earliest_without_removing_it() -> None:
    heap = TriggerHeap(at("2026-01-01T00:00:00+00:00"))
    heap.insert(at("2026-01-01T00:01:00+00:00"), 0, RecurringMessage.every(60, Plain()))

    assert heap.top()[1] == 0
    assert heap
