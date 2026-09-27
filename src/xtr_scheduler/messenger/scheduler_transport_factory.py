"""Builds ``schedule://<name>`` transports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, final
from urllib.parse import urlsplit

from typing_extensions import override
from xtr_messenger import TransportFactoryInterface
from xtr_messenger.transport.transport_options import as_bool, reject_unknown_options

from xtr_scheduler.exception import InvalidArgumentError
from xtr_scheduler.schedule_provider_locator import ScheduleProviderLocator

from ._located_message_generator import LocatedMessageGenerator
from .scheduler_transport import SchedulerTransport

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_messenger import Dsn, SenderInterface, TransportConfig

    from xtr_scheduler.schedule_provider_interface import ScheduleProviderInterface

__all__ = ["SCHEDULE_OPTIONS", "SCHEDULE_SCHEME", "SchedulerTransportFactory"]

SCHEDULE_SCHEME: Final = "schedule"

#: Settings a ``schedule://`` transport accepts.
SCHEDULE_OPTIONS: Final = ("use_messenger_routing",)


@final
class SchedulerTransportFactory(TransportFactoryInterface):
    """Builds a :class:`SchedulerTransport` for each ``schedule://<name>`` DSN.

    ``<name>`` names a schedule among ``providers``. Built with none — as
    transport discovery builds it — it serves the schedules declared with
    :func:`~xtr_scheduler.decorator.as_schedule` and the task decorators,
    building each provider with no arguments.

    ``?use_messenger_routing=true`` on a DSN hands every message to routing
    rather than to the worker consuming the transport.
    """

    __slots__ = ("_clock", "_providers", "_use_messenger_routing")

    def __init__(
        self,
        providers: ScheduleProviderLocator | Mapping[str, ScheduleProviderInterface] | None = None,
        *,
        clock: ClockInterface | None = None,
        use_messenger_routing: bool = False,
    ) -> None:
        """Serve the schedules in ``providers``, by name, reading time from ``clock``.

        ``use_messenger_routing`` is the default for a DSN that does not say.
        """
        if isinstance(providers, Mapping):
            providers = ScheduleProviderLocator(providers)
        self._providers = providers
        self._clock = clock
        self._use_messenger_routing = use_messenger_routing

    @override
    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == SCHEDULE_SCHEME

    @override
    def create(self, group: Mapping[str, TransportConfig]) -> Mapping[str, SenderInterface]:
        """Build a transport for each schedule ``group`` names.

        Raises:
            InvalidArgumentError: If a DSN names no schedule, or one that is
                not known.
            UnknownTransportOptionError: If a DSN carries a setting this
                transport does not accept.
        """
        providers = self._resolved_providers()
        built: dict[str, SenderInterface] = {}
        for transport_name, spec in group.items():
            reject_unknown_options(SCHEDULE_SCHEME, spec.settings, SCHEDULE_OPTIONS)
            name = _schedule_name(spec.parsed.connection)
            if not providers.has(name):
                raise InvalidArgumentError(f'The schedule "{name}" is not found.')
            routing = as_bool(spec.settings, "use_messenger_routing", self._use_messenger_routing)
            built[transport_name] = SchedulerTransport(
                LocatedMessageGenerator(providers, name, self._clock),
                name=transport_name,
                use_messenger_routing=routing,
                clock=self._clock,
            )
        return built

    def _resolved_providers(self) -> ScheduleProviderLocator:
        if self._providers is None:
            from xtr_scheduler.registry.declared_schedules import (  # noqa: PLC0415 — declarations are read when first needed
                declared_schedules,
            )

            self._providers = declared_schedules()
        return self._providers


def _schedule_name(connection: str) -> str:
    """Return the schedule a ``schedule://<name>`` DSN names.

    Raises:
        InvalidArgumentError: If it names none.
    """
    name = urlsplit(connection).netloc
    if not name:
        raise InvalidArgumentError(
            f'The schedule DSN "{connection}" must contain a name, e.g. "schedule://default".'
        )
    return name
