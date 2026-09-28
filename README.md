<div align="center">

# xtr-scheduler

**Recurring messages on xtr-messenger: cron and periodic triggers, catch-up after downtime, locks and saved state across restarts.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"Every night at three" and "every ten minutes" sound simple until a worker restarts at 02:59,
two replicas both think it is their turn, or the machine was off for an hour and nobody knows
which runs were missed.

A schedule here is a set of **recurring messages** — a message and when to send it. A
**scheduler transport** turns the schedule into messages as they fall due, and a messenger
worker consumes it like any other transport: each message is handled there, or sent on to
wherever routing puts it — a RabbitMQ queue and its worker pool, say.

- ⏱️ **Nothing is sent twice, nothing is lost** — every message is recorded as sent before the
  next is produced; a restarted worker resumes exactly where the last one stopped.
- 🔁 **Catch-up** — after downtime every missed run is sent, oldest first, or only the latest
  of each when the schedule asks.
- 🔒 **One sender** — give a schedule an [xtr-lock](../xtr-lock) lock and only the process
  holding it sends; give it an [xtr-cache](../xtr-cache) pool and its progress survives restarts.
- 🧭 **Cron, intervals, or your own** — hashed cron (`#daily`) spreads tasks across the hour;
  jitter spreads a fleet; triggers are a one-method protocol.
- 🧪 **Testable in no time** — time comes from [xtr-clock](../xtr-clock), so a test freezes it
  and steps through a day instantly.

## Install

```sh
uv add "xtr-scheduler[cron]"            # + cron expressions
uv add "xtr-scheduler[cron,di]"         # + a SchedulerBundle for xtr-dependency-injection
uv add "xtr-scheduler[cron,console]"    # + the debug:scheduler console command
```

| Extra | Brings | For |
| --- | --- | --- |
| *(none)* | `xtr-messenger`, `xtr-clock`, `xtr-lock`, `xtr-cache-contracts`, `xtr-event-dispatcher` | Intervals, the transport, events |
| `cron` | `croniter` | `RecurringMessage.cron(...)` and `@as_cron_task` |
| `di` | `xtr-dependency-injection` | A `SchedulerBundle` |
| `console` | `xtr-console` | `debug:scheduler` |

Requires Python 3.11+.

## Quick start

```python
from xtr_messenger import MessageBusConfig, TransportConfig, WorkerFactory
from xtr_scheduler import RecurringMessage, Schedule
from xtr_scheduler.messenger import SchedulerTransportFactory

schedule = Schedule(
    RecurringMessage.cron("0 3 * * *", PurgeSessions(), timezone="Europe/Bucharest"),
    RecurringMessage.every("10 minutes", RefreshRates()),
)

config = MessageBusConfig(transports={"scheduler": TransportConfig("schedule://default")})
factories = [SchedulerTransportFactory({"default": schedule})]

await WorkerFactory(config, factories).worker(["scheduler"]).run()
```

The worker handles each message as it falls due, with whatever
`@as_message_handler` declares for its type. `schedule://default` names the schedule.

### Sending runs on

A worker consuming a schedule is one process. To have the runs handled on your worker pool
instead, wrap the message in a `RedispatchMessage` — it is dispatched again, through routing:

```python
from xtr_messenger import RedispatchMessage

RecurringMessage.every(
    "1 hour", RedispatchMessage(BuildReport())
)  # where routing sends BuildReport
RecurringMessage.every("1 hour", RedispatchMessage(BuildReport(), "reports"))  # to "reports" only
```

`schedule://default?use_messenger_routing=true` does this for every message of the schedule.
The message arrives carrying a `ScheduledStamp` — which schedule, which run — on whichever
worker handles it.

## Recurring messages

| Build | Runs |
| --- | --- |
| `RecurringMessage.every(60, msg)` | every 60 seconds |
| `RecurringMessage.every("10 minutes", msg)` | every 10 minutes — `second`, `minute`, `hour`, `day`, `week`, `fortnight`, `month`, `year`, plural or not |
| `RecurringMessage.every("PT1H", msg)` | ISO 8601 durations, converted to seconds |
| `RecurringMessage.every(timedelta(hours=1), msg)` | a `timedelta` |
| `RecurringMessage.cron("0 3 * * *", msg, timezone=...)` | a cron expression, on the clock of `timezone` — the clock's own zone when omitted |
| `RecurringMessage.trigger(trigger, msg)` | any `TriggerInterface` |
| `.with_jitter(30)` | each run delayed at random by up to 30 seconds |

Seconds, minutes and hours are exact: runs fall exactly that far apart. Days, weeks, months and
years follow the calendar — "every day" at 09:00 stays at 09:00 across a clock change, and "every
month" from the 31st runs on the last day of shorter months. `every(..., from_=..., until=...)`
bounds an interval; left without `from_`, it counts from when the schedule first ran.

**Hashed cron** puts `#` where a value would go: `"# # * * *"` is once a day at a minute and hour
picked for that message, from its string form — the same pick in every process, a different one
per message, so a hundred daily tasks do not all start at midnight. `#(0-5)` picks within a range,
and `#hourly`, `#daily`, `#weekly`, `#monthly`, `#yearly` and `#midnight` are shorthands.

A message may be a `MessageProviderInterface` instead, deciding the messages of each run —
`CallbackMessageProvider(lambda context: [Invoice(t) for t in active_tenants()])`.

Triggers are strict: the next run is always strictly after the one asked about, or `None` to
stop. `CallbackTrigger`, `ExcludeTimeTrigger` (skip a window) and `JitterTrigger` compose with
the rest.

## A schedule's behaviour

```python
schedule = (
    Schedule(...)
    .lock(lock_factory.create_lock("schedule-default"))  # only the holder sends
    .stateful(cache_pool)  # progress survives restarts
    .process_only_last_missed_run()  # after downtime, the latest run only
)
```

| | No cache | With `.stateful(pool)` |
| --- | --- | --- |
| **No lock** | Every process sends every run; a restart starts from now | Every process sends; a restart resumes |
| **With `.lock(lock)`** | One process sends; another taking over starts from now | One process sends; another taking over resumes |

Between runs the lock is kept until the next one is due. A worker that stops gives it back, so
the next process takes over at once; one that crashes leaves it to run out.

A pool that fails to save stops the schedule with `SchedulerRuntimeError` rather than carrying on:
going on would send every run again after a restart, or nothing at all.

Adding or removing messages while the schedule runs is safe — what already ran is not sent again.

## Events

```python
schedule.before(lambda event: event.should_cancel(not maintenance_window_open()))
schedule.after(lambda event: metrics.record(event.context.id, event.result))
schedule.on_failure(lambda event: alert(event.message, event.error))
```

`PreRunEvent` (a listener may cancel the run — the worker then skips the message),
`PostRunEvent` (with what handling returned) and `FailureEvent`. They come from the worker that
handles the message, through `DispatchSchedulerEventListener` subscribed to the messenger's worker
events — the application's dispatcher hears them first, then the schedule's own listeners. A run
redispatched through routing is announced once, by the worker that handles it where it lands: one
sent to `sync://`, or to a transport no worker with the listener consumes, is not announced.

## Declaring tasks

A class or function can be a task without writing a schedule:

```python
from xtr_scheduler.decorator import as_cron_task, as_periodic_task, as_schedule


@as_cron_task("0 3 * * *", timezone="Europe/Bucharest")
async def purge_sessions() -> None: ...


@as_periodic_task("10 minutes", jitter=30, transports="jobs")
class RefreshRates:
    async def __call__(self) -> None: ...


class Maintenance:
    @as_cron_task("#daily")
    async def vacuum(self) -> None: ...

    @as_cron_task("#weekly", arguments=["full"])
    async def reindex(self, mode: str) -> None: ...
```

Each run sends a `ServiceCallMessage` naming the target, handled by calling it. `schedule=` picks
the schedule (`"default"` otherwise), `method=` the method of a class, `arguments=` JSON values to
call it with, and `transports=` sends the runs there to be handled rather than where the
schedule is consumed. Stack the decorators for several runs.

`@as_schedule("name")` declares a class providing a whole schedule; tasks on the same name join it.

Without a container, `schedule://<name>` serves the declared schedules as discovery finds the
transport — every class is built with no arguments.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing it undoes.

- **Install** — `uv add "xtr-scheduler[cron,di,console]"`.
- **Activate** — `SchedulerBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_scheduler.bundle`.
- **Brings along** — the messenger bundle; the event dispatcher and console bundles, when
  those packages are installed.
- **Configure** — optional: with no configuration every task joins a plain `default`
  schedule, which keeps no state and takes no lock. For one that resumes after a restart and
  sends each run once, copy [a starter schedule](#a-starter-schedule) into
  `<app>/schedule.py` and activate the cache and lock bundles it needs.
- **Environment** — nothing.
- **Ignore** — nothing.
- **Run** — a worker is `<script> messenger:consume scheduler_default`.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/schedule.py` and every
  `@as_cron_task` / `@as_periodic_task`, then `uv remove xtr-scheduler`.
- **Check** — `debug:scheduler` lists each schedule with every message's next run.

## Kernel / bundle

```python
# app/bundles.py
from xtr_scheduler.bundle import SchedulerBundle

BUNDLES = {SchedulerBundle: {"all": True}}
```

The bundle brings the messenger bundle with it. Every schedule and task its scan finds is built
by the container with its dependencies — and a function task may ask for services with
`Injected[...]`. Each schedule becomes consumable as `scheduler_<name>` without configuring a
transport:

```sh
uv run python -m app.console messenger:consume scheduler_default
```

Configure `scheduler_<name>` yourself — `TransportConfig("schedule://default?use_messenger_routing=true")`
— and yours is used instead. `SchedulerConfig(use_messenger_routing=True)` sets it for all of them.

### A starter schedule

Tasks alone need no schedule class: the bundle gathers them into a plain `Schedule` per name.
A plain schedule keeps no state and takes no lock, though — a restarted worker starts from
now, forgetting what it missed, and two workers both send every run. To choose, write the
schedule the tasks join; this is a good first one to copy into the application:

```python
# app/schedule.py
from typing import Annotated

from typing_extensions import override
from xtr_cache_contracts import CacheInterface
from xtr_dependency_injection import Target
from xtr_lock import LockFactory
from xtr_scheduler import Schedule, ScheduleProviderInterface
from xtr_scheduler.decorator import as_schedule


@as_schedule()  # "default" — every task not naming a schedule joins this one
class AppSchedule(ScheduleProviderInterface):
    def __init__(
        self,
        cache: Annotated[CacheInterface, Target("scheduler")],
        locks: LockFactory,
    ) -> None:
        self._schedule = (
            Schedule()  # add recurring messages of your own here
            .stateful(cache)  # a restart resumes, sending what was missed
            .process_only_last_missed_run()  # ...only the latest run of each, though
            .lock(locks.create_lock("scheduler-default"))  # one worker sends, however many run
        )

    @override
    def get_schedule(self) -> Schedule:
        return self._schedule
```

The `scheduler` pool it asks for exists when the [cache bundle](../xtr-cache) is active: the
scheduler bundle adds it on the app pool's adapter, under a namespace of its own, so checkpoints
never mix with the application's values and `cache:pool:clear scheduler` clears them alone.
Configure a `scheduler` pool yourself — `CacheConfig(pools={"scheduler": "redis://…"})` — and
yours is used instead. Nothing uses the pool on its own. `LockFactory` comes from the
[lock bundle](../xtr-lock): its default resource keeps file locks, enough for workers on one
machine; give it a Redis store for several.

`env="prod"` on a task keeps it to those environments, the way `@when` does for a service; its
schedule stays, empty if nothing else is on it, so a worker can be started for it anywhere. With
the event dispatcher bundle active, runs are announced; with the console bundle,
`debug:scheduler` lists each schedule with every message's next run:

```
┌───────────────────────────────────┬─────────────────┬───────────────────────────┬─────────────┐
│ Trigger                           │ Provider        │ Next Run On               │ Next Run In │
├───────────────────────────────────┼─────────────────┼───────────────────────────┼─────────────┤
│ every 60 seconds                  │ Named (ping)    │ 2026-01-01T00:01:00+00:00 │ 1 min       │
│ 0 3 * * * with 0-30 second jitter │ Named (nightly) │ 2026-01-01T03:00:27+00:00 │ 3 h, 27 s   │
└───────────────────────────────────┴─────────────────┴───────────────────────────┴─────────────┘
```

`--date` computes from another date, `--all` shows messages that never run again, `--sort`
orders by next run. A stateful schedule is listed from where its saved state says it got to.

## Without a message bus

`Scheduler` runs schedules in-process, handing each message to a handler for its exact type:

```python
from xtr_scheduler.scheduler import Scheduler

scheduler = Scheduler({PurgeSessions: purge}, [schedule], event_dispatcher=events)
await scheduler.run()  # until scheduler.stop()
```

With a dispatcher, a `FailureEvent` listener may ignore an error rather than let it stop the run. When `run()` returns, however it
returns, every schedule's lock is handed back, so another process takes over at once;
`await scheduler.close()` does the same for a scheduler that was never run.

## Known limitations

- Cron expressions are read by croniter 6: a clock change that is not a whole hour can shift a
  match, and stepped ranges that wrap around are read as croniter reads them.
- Interval strings take one unit — `"90 minutes"`, not `"1 hour 30 minutes"`.
- A `RedispatchMessage` holds an envelope and lives in the process that creates it; the message
  inside is what crosses a transport.

## Errors

Everything the library raises derives from `SchedulerError`: `InvalidArgumentError` (a value it
cannot use — an interval, a date, an unknown schedule), `SchedulerLogicError` (a trigger that does
not move forward, a message added twice, a transport asked to send) and `SchedulerRuntimeError`
(state that could not be saved).

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-scheduler`; run the commands below from there. The `python-xtr-scheduler` repository
is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
