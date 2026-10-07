"""A message sent over and over, on a trigger."""

from __future__ import annotations

import base64
import hashlib
import json
from contextlib import suppress
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import default_codecs, name_of

from ._time import FAR_FUTURE
from .exception import InvalidArgumentError
from .trigger.cron_expression_trigger import CronExpressionTrigger
from .trigger.jitter_trigger import JitterTrigger
from .trigger.message_provider_interface import MessageProviderInterface
from .trigger.periodical_trigger import PeriodicalTrigger
from .trigger.static_message_provider import StaticMessageProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime, timedelta, tzinfo

    from .generator.message_context import MessageContext
    from .trigger.trigger_interface import TriggerInterface

__all__ = ["RecurringMessage"]

_PROVIDER_ID_LENGTH = 7


@final
class RecurringMessage(MessageProviderInterface):
    """What to send, and when: a message provider on a trigger.

    Build one with :meth:`every`, :meth:`cron` or :meth:`trigger`. Its
    :attr:`id` is derived from what it sends and when, so the same recurring
    message declared in two processes — or in one process across restarts —
    is recognised as the same one, which is what lets saved state resume it.
    """

    __slots__ = ("_id", "_provider", "_trigger")

    def __init__(self, trigger: TriggerInterface, provider: MessageProviderInterface) -> None:
        """Send what ``provider`` produces whenever ``trigger`` fires."""
        self._trigger = trigger
        self._provider = provider
        self._id: str | None = None

    @classmethod
    def every(
        cls,
        frequency: float | str | timedelta,
        message: object,
        *,
        from_: datetime | str | None = None,
        until: datetime | str = FAR_FUTURE,
    ) -> RecurringMessage:
        """Send ``message`` every ``frequency`` — see :class:`PeriodicalTrigger` for the forms.

        Raises:
            InvalidArgumentError: If the frequency or a date cannot be used.
        """
        return cls.trigger(PeriodicalTrigger(frequency, from_, until), message)

    @classmethod
    def cron(
        cls,
        expression: str,
        message: object,
        *,
        timezone: tzinfo | str | None = None,
    ) -> RecurringMessage:
        """Send ``message`` whenever ``expression`` matches, on the clock of ``timezone``.

        A hashed expression (``"# # * * *"``) picks its values from the
        message's string form, so the message must define ``__str__``.

        Raises:
            InvalidArgumentError: If the expression is hashed and the message
                has no string form of its own, or the expression is invalid.
        """
        if not CronExpressionTrigger.is_hashed(expression):
            return cls.trigger(
                CronExpressionTrigger.from_expression(expression, None, timezone), message
            )
        if not _has_own_str(message):
            raise InvalidArgumentError(
                'A message must be stringable to use "hashed" cron expressions.'
            )
        return cls.trigger(
            CronExpressionTrigger.from_expression(expression, str(message), timezone), message
        )

    @classmethod
    def trigger(cls, trigger: TriggerInterface, message: object) -> RecurringMessage:
        """Send ``message`` whenever ``trigger`` fires.

        ``message`` may be a :class:`MessageProviderInterface`, producing
        the messages of each run itself; anything else is sent as it is.
        """
        if isinstance(message, MessageProviderInterface):
            return cls(trigger, message)
        description = type(message).__qualname__
        if _has_own_str(message):
            with suppress(Exception):  # a description is only a label; never fail over one
                description += f" ({message})"
        return cls(trigger, StaticMessageProvider([message], _provider_id(message), description))

    def with_jitter(self, max_seconds: int = 60) -> RecurringMessage:
        """Return this recurring message, each run delayed at random by up to ``max_seconds``."""
        jitter = JitterTrigger(self._trigger, max_seconds, key=self._provider.id)
        return RecurringMessage(jitter, self._provider)

    @property
    @override
    def id(self) -> str:
        """Return what identifies this recurring message within a schedule.

        Derived from what it sends and how its trigger describes itself, so it
        is the same in every process.
        """
        if self._id is None:
            identity = "".join(
                (
                    _qualified(type(self._provider)),
                    self._provider.id,
                    _qualified(type(self._trigger)),
                    str(self._trigger),
                )
            )
            self._id = hashlib.blake2b(identity.encode(), digest_size=8).hexdigest()
        return self._id

    def get_provider(self) -> MessageProviderInterface:
        """Return what produces the messages of each run."""
        return self._provider

    def get_trigger(self) -> TriggerInterface:
        """Return what says when the message runs.

        A method rather than a property because :meth:`trigger` is the
        factory building a recurring message from one.
        """
        return self._trigger

    @override
    def get_messages(self, context: MessageContext, /) -> AsyncIterator[object]:
        return self._provider.get_messages(context)

    @override
    def __repr__(self) -> str:
        return f"<RecurringMessage {self.id}: {self._provider} on {self._trigger}>"


def _has_own_str(message: object) -> bool:
    return type(message).__str__ is not object.__str__


def _qualified(kind: type) -> str:
    return f"{kind.__module__}.{kind.__qualname__}"


def _provider_id(message: object) -> str:
    """Return a short id for ``message``, the same in every process that builds it alike.

    Built from the message's wire form when a codec handles it — the same
    form it crosses a transport in — and from its ``repr`` otherwise, which
    for a dataclass is stable too.
    """
    kind = type(message)
    codec = next((codec for codec in default_codecs() if codec.supports(kind)), None)
    body = repr(message)
    if codec is not None:
        with suppress(Exception):  # a message the codec cannot carry keeps its repr
            body = json.dumps(codec.encode(message), sort_keys=True)
    digest = hashlib.blake2b(f"{name_of(kind)}\n{body}".encode(), digest_size=16).digest()
    return base64.b64encode(digest).decode()[:_PROVIDER_ID_LENGTH].translate(_URL_SAFE)


_URL_SAFE = str.maketrans("/+", "._")
