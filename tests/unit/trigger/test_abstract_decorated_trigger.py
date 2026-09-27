"""A trigger that changes what another trigger answers."""

from __future__ import annotations

from tests.support.dates import at
from xtr_scheduler.trigger import (
    CallbackTrigger,
    ExcludeTimeTrigger,
    JitterTrigger,
    PeriodicalTrigger,
)


def test_inner_is_the_trigger_at_the_bottom() -> None:
    periodical = PeriodicalTrigger(60)
    decorated = JitterTrigger(
        ExcludeTimeTrigger(periodical, "2026-01-01T00:00Z", "2026-01-02T00:00Z")
    )

    assert decorated.inner() is periodical
    assert decorated.decorated is not periodical


def test_decorators_are_listed_outermost_first() -> None:
    excluding = ExcludeTimeTrigger(PeriodicalTrigger(60), "2026-01-01T00:00Z", "2026-01-02T00:00Z")
    jitter = JitterTrigger(excluding)

    assert list(jitter.decorators()) == [jitter, excluding]


def test_the_starting_point_reaches_the_trigger_at_the_bottom() -> None:
    periodical = PeriodicalTrigger(60)
    decorated = ExcludeTimeTrigger(periodical, "2030-01-01T00:00Z", "2030-01-02T00:00Z")

    decorated.continue_(at("2026-01-01T00:00:10+00:00"))

    assert periodical.get_next_run_date(at("2026-01-01T00:05:00+00:00")) == at(
        "2026-01-01T00:05:10+00:00"
    )


def test_a_trigger_with_no_starting_point_is_left_alone() -> None:
    decorated = JitterTrigger(CallbackTrigger(lambda _run: None, "never"))

    decorated.continue_(at("2026-01-01T00:00:00+00:00"))

    assert str(decorated) == "never with 0-60 second jitter"
