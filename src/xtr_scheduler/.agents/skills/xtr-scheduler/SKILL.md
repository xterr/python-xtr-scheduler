---
name: xtr-scheduler
description: How to run recurring work with xtr-scheduler — cron expressions, fixed intervals, catch-up after downtime, a lock so one process sends, and saved state across restarts, all on xtr-messenger. Use when something must happen "every night at three", "every ten minutes" or "once a week", when writing a cron job, a periodic job, a background heartbeat, a nightly purge or a recurring report, when a scheduled run must not fire twice across replicas or must resume after a restart, when adding SchedulerBundle to an application on xtr-dependency-injection, or when running the scheduler worker with messenger:consume.
---

# xtr-scheduler

A schedule is a set of recurring messages: a message, and when to send it. A scheduler transport
turns the schedule into messages as they fall due, and an xtr-messenger worker consumes it like
any other transport. Handlers, transports and routing are xtr-messenger's job — see the
`xtr-messenger` skill for those.

## Quick reference

- Declare work with `@as_cron_task(...)` / `@as_periodic_task(...)` from `xtr_scheduler.decorator`;
  a whole schedule with `@as_schedule("name")` on a `ScheduleProviderInterface`.
- Build messages by hand with `RecurringMessage.every(...)`, `.cron(...)`, `.trigger(...)` on a
  `Schedule` from `xtr_scheduler`.
- `.lock(lock)` so one process sends, `.stateful(pool)` so a restart resumes,
  `.process_only_last_missed_run()` to skip a backlog.
- Run it: `<script> messenger:consume scheduler_<name>`.
- Inspect it: `debug:scheduler` (needs the `console` extra).
- Cron needs the `cron` extra: `uv add "xtr-scheduler[cron,di,console]"`.

## Declare a task

The usual way. No schedule class needed; every task joins the schedule named by `schedule=`
(`"default"` otherwise).

```python
from typing import Annotated

from xtr_dependency_injection import Injected, Target
from xtr_scheduler.decorator import as_cron_task, as_periodic_task


@as_periodic_task("10 minutes", jitter=30)
async def refresh_rates(rates: Injected[RateService]) -> None: ...


@as_cron_task("0 3 * * *", timezone="Europe/Bucharest", env="prod", transports="jobs")
async def purge_abandoned_carts() -> None: ...


@as_periodic_task("1 hour", method="build")
class CatalogReport:
    def __init__(self, catalog: Annotated[CatalogInterface, Target("books")]) -> None: ...

    def build(self) -> int: ...


class Housekeeping:  # a decorated method is a task calling that method
    @as_cron_task("#daily")
    def forget_queries(self) -> str: ...

    @as_cron_task("#weekly", arguments=["full"])
    def reindex(self, mode: str) -> str: ...
```

| Keyword | Does |
| --- | --- |
| `schedule="reports"` | Joins that schedule instead of `default` |
| `method="build"` | Calls that method of the class; `__call__` when omitted |
| `arguments=[...]` | Positional arguments of each call, JSON values |
| `transports="jobs"` | Sends the run there to be handled, not where the schedule is consumed |
| `env="prod"` or `env=["dev", "test"]` | Only in those environments |
| `jitter=30` | Each run delayed at random by up to 30 seconds |
| `timezone="Europe/Paris"` (cron) | The zone the expression is read in |
| `from_=`, `until=` (periodic) | Bounds the interval |

Each run sends a `ServiceCallMessage` naming the target; the package's handler calls it. Stack the
decorators for several runs of one target. With a container, a task class is built with its
dependencies and a task function may ask for services.

## Cron or interval

| Build | Runs |
| --- | --- |
| `RecurringMessage.every(60, msg)` | every 60 seconds |
| `RecurringMessage.every("10 minutes", msg)` | `sec`, `min`, `hour`, `day`, `week`, `fortnight`, `month`, `year`, plural or not |
| `RecurringMessage.every("PT1H", msg)` | an ISO 8601 duration |
| `RecurringMessage.every(timedelta(hours=1), msg)` | a `timedelta` |
| `RecurringMessage.cron("0 3 * * *", msg, timezone="UTC")` | a cron expression |
| `RecurringMessage.trigger(my_trigger, msg)` | any `TriggerInterface` |
| `.with_jitter(30)` | each run delayed at random by up to 30 seconds |

- Seconds, minutes and hours are exact. Days, weeks, months and years follow the calendar: "every
  day" at 09:00 stays at 09:00 across a clock change, "every month" from the 31st lands on the
  last day of shorter months.
- An interval string takes one unit: `"90 minutes"`, never `"1 hour 30 minutes"`.
- Hashed cron spreads a fleet: `"# # * * *"` is once a day at a minute and hour picked from the
  message's string form, the same pick in every process. `#(0-5)` picks in a range; `#hourly`,
  `#daily`, `#weekly`, `#monthly`, `#yearly`, `#midnight` are shorthands. A hashed expression
  needs a message with its own `__str__`.
- Composable triggers live in `xtr_scheduler.trigger`: `CallbackTrigger`, `ExcludeTimeTrigger`,
  `JitterTrigger`, `PeriodicalTrigger`, `CronExpressionTrigger`.
- To decide the messages of each run, pass a `MessageProviderInterface` instead of a message —
  `CallbackMessageProvider(lambda context: [Invoice(t) for t in active_tenants()])`.

## Write the schedule itself

Tasks alone get a plain schedule: no lock, no state. A restarted worker starts from now, and two
workers both send every run. Declare the schedule they join to choose otherwise.

```python
# app/schedule.py
from typing import Annotated

from typing_extensions import override
from xtr_cache_contracts import CacheInterface
from xtr_dependency_injection import Target
from xtr_lock import LockFactory
from xtr_scheduler import RecurringMessage, Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule


@as_schedule()  # "default" — every task not naming a schedule joins this one
class AppSchedule(ScheduleProviderInterface):
    def __init__(
        self,
        cache: Annotated[CacheInterface, Target("scheduler")],
        locks: LockFactory,
    ) -> None:
        self._schedule = (
            Schedule(RecurringMessage.cron("#hourly", RestockCheck()))
            .stateful(cache)  # a restart resumes and sends what was missed
            .process_only_last_missed_run()  # ...the latest run of each only
            .lock(locks.create_lock("scheduler-default"))  # one sender, however many workers
        )

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule
```

## Catch-up, locks and state

| | No cache | With `.stateful(pool)` |
| --- | --- | --- |
| **No lock** | Every process sends every run; a restart starts from now | Every process sends; a restart resumes |
| **With `.lock(lock)`** | One process sends; another taking over starts from now | One process sends; another taking over resumes |

- Every message is recorded as sent before the next is produced, so nothing goes twice.
- After downtime every missed run is sent oldest first, unless
  `.process_only_last_missed_run()` asks for the latest of each.
- The lock is kept between runs. A worker stopping gives it back at once; one that crashes leaves
  it to lapse. Adding or removing messages while the schedule runs is safe.
- A pool that cannot save stops the schedule with `SchedulerRuntimeError` rather than carrying on.

## Have the runs handled elsewhere

The worker consuming a schedule handles its messages itself. Wrap a message to send it on through
routing instead:

```python
from xtr_messenger import RedispatchMessage

RecurringMessage.every("1 hour", RedispatchMessage(BuildReport()))  # where routing sends it
RecurringMessage.every("1 hour", RedispatchMessage(BuildReport(), "reports"))  # to "reports"
```

`SchedulerConfig(use_messenger_routing=True)`, or a DSN
`schedule://default?use_messenger_routing=true`, does it for a whole schedule. The message carries
a `ScheduledStamp` (`name`, `id`, `trigger`, `triggered_at`, `next_trigger_at`) wherever it lands.

## React to a run

`schedule.before(...)`, `.after(...)`, `.on_failure(...)` register listeners for `PreRunEvent`,
`PostRunEvent` and `FailureEvent` (`xtr_scheduler.event`), announced by the worker that handles the
message. The application's dispatcher hears each first, then the schedule's own listeners.

```python
schedule.before(lambda event: event.should_cancel(not window_open()))  # the worker skips it
schedule.after(lambda event: metrics.record(event.context.id, event.result))
schedule.on_failure(lambda event: alert(event.message, event.error))
```

A run sent to `sync://`, or to a transport no worker with that listener consumes, is not announced.

## Without a message bus

`Scheduler` runs schedules in this process, handing each message to the handler for its exact type.
The dispatcher you pass is the one announcing every run; `await scheduler.close()` hands back the
locks of a scheduler that was never run.

```python
from xtr_scheduler.scheduler import Scheduler

scheduler = Scheduler({PurgeSessions: purge}, [schedule], event_dispatcher=events)
await scheduler.run()  # until scheduler.stop()
```

## Testing

Freeze time and step through a day instantly: a `MessageGenerator` yields what is due, so no worker
and no bus are needed.

```python
from xtr_clock import MockClock
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.generator import MessageGenerator


async def test_it_sends_every_ten_minutes() -> None:
    clock = MockClock("2026-01-01 02:55:00")
    generator = MessageGenerator(
        Schedule(RecurringMessage.every("10 minutes", Refresh())), "t", clock
    )

    assert [m async for _c, m in generator.get_messages()] == []  # nothing due yet

    clock.sleep(1200)  # twenty minutes, instantly
    due = [(c.triggered_at.isoformat(), m) async for c, m in generator.get_messages()]

    assert [t for t, _m in due] == ["2026-01-01T03:05:00+00:00", "2026-01-01T03:15:00+00:00"]
    await generator.close()  # hands the lock back
```

Give the `Schedule` an `ArrayAdapter` pool through `.stateful(...)` to test catch-up, and an
in-memory `Lock` through `.lock(...)` to test a takeover.

## Use in an application

1. **Install** — `uv add "xtr-scheduler[cron,di,console]"`; add xtr-cache for the `scheduler` pool a
   schedule keeps its state in, and xtr-lock for `LockFactory`.
2. **Activate** — `SchedulerBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`
   (`from xtr_scheduler.bundle import SchedulerBundle`).
3. **Brings along** — the messenger bundle always; the event dispatcher and console bundles when
   those packages are installed.
4. **Configure** — optional; with no configuration every task joins a plain `default` schedule:

   ```python
   # <app>/config/scheduler.py
   from xtr_dependency_injection import configure
   from xtr_scheduler.bundle import SchedulerConfig


   @configure
   def scheduler() -> SchedulerConfig:
       return SchedulerConfig(use_messenger_routing=True)
   ```

   For state and a lock, write the schedule above into `<app>/schedule.py`.
5. **Environment** — nothing.
6. **Run** — `uv run python -m app.console messenger:consume scheduler_default`. Each schedule is
   consumable as `scheduler_<name>` with no transport configured; configure one of that name
   yourself and yours wins. Due runs are asked for once a second, so a run may start a second late;
   nothing is skipped.
7. **Check** — `debug:scheduler` lists every schedule with each message's next run. `--date`
   computes from another date, `--all` shows messages that never run again, `--sort` orders by next
   run.
8. **Remove** — drop the `BUNDLES` entry, delete `<app>/schedule.py` and every `@as_cron_task` /
   `@as_periodic_task`, then `uv remove xtr-scheduler`.

## Errors

All derive from `SchedulerError` (`xtr_scheduler.exception`):

- `InvalidArgumentError` — a value it cannot use: an unreadable interval, a naive date, an unknown
  schedule name, a hashed cron expression on a message with no `__str__`.
- `SchedulerLogicError` — a trigger that does not move forward, a message added twice, a scheduler
  transport asked to send.
- `SchedulerRuntimeError` — state that could not be saved.

## Do not

- Do not run two workers on one schedule without `.lock(...)`; both send every run.
- Do not expect a plain schedule to catch up after downtime — without `.stateful(...)` it starts
  from now.
- Do not write a multi-unit interval (`"1 hour 30 minutes"`); use one unit or a `timedelta`.
- Do not use `RecurringMessage.cron` or `@as_cron_task` without the `cron` extra installed.
- Do not send a `RedispatchMessage` across a broker: it lives in the process that creates it; the
  message inside is what travels.
- Do not read the system clock in a scheduled task; take a `ClockInterface` so a test can freeze it.
