"""What a task decorator declared."""

from __future__ import annotations

from xtr_scheduler.registry import TaskDeclaration
from xtr_scheduler.trigger import JitterTrigger, StaticMessageProvider


def test_a_cron_task_calls_its_target_on_the_expression() -> None:
    recurring = TaskDeclaration(kind="cron", expression="0 3 * * *").recurring_message("app.Job")

    assert str(recurring.get_trigger()) == "0 3 * * *"
    assert str(recurring.get_provider()) == "ServiceCallMessage (@app.Job)"


def test_a_periodic_task_calls_the_method_with_its_arguments() -> None:
    declaration = TaskDeclaration(kind="every", frequency=60, method="build", arguments=("eu",))

    recurring = declaration.recurring_message("app.Reports")

    assert str(recurring.get_trigger()) == "every 60 seconds"
    assert str(recurring.get_provider()) == "ServiceCallMessage (@app.Reports::build)"


def test_a_hashed_cron_task_picks_from_the_call_it_makes() -> None:
    first = TaskDeclaration(kind="cron", expression="#daily").recurring_message("app.A")
    second = TaskDeclaration(kind="cron", expression="#daily").recurring_message("app.B")

    assert str(first.get_trigger()) != str(second.get_trigger())


def test_a_task_with_transports_is_sent_there() -> None:
    declaration = TaskDeclaration(kind="every", frequency=60, transports=("reports",))

    recurring = declaration.recurring_message("app.Reports")

    provider = recurring.get_provider()
    assert isinstance(provider, StaticMessageProvider)
    assert str(provider) == "RedispatchMessage (@app.Reports via reports)"


def test_jitter_wraps_the_trigger() -> None:
    declaration = TaskDeclaration(kind="every", frequency=60, jitter=15)

    assert isinstance(declaration.recurring_message("app.Job").get_trigger(), JitterTrigger)


def test_a_task_exists_in_the_environments_it_names_or_in_all() -> None:
    assert TaskDeclaration(kind="every").exists_in("test")
    assert TaskDeclaration(kind="every", env=("prod",)).exists_in("prod")
    assert not TaskDeclaration(kind="every", env=("prod",)).exists_in("test")
