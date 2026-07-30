from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from authz_policy import (
    CompanyCapability,
    CompanyState,
    evaluate_company_capability,
)


MAX_REMINDERS = 20
MAX_MESSAGE_LENGTH = 5000


class ReminderUnit(str, Enum):
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


class ReminderReasonCode(str, Enum):
    DUE = "DUE"
    NOT_DUE = "NOT_DUE"
    ALREADY_SENT = "ALREADY_SENT"
    REMINDER_DISABLED = "REMINDER_DISABLED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_NOT_ACTIVE = "SESSION_NOT_ACTIVE"
    APPLICATION_RECEPTION_DISABLED = "APPLICATION_RECEPTION_DISABLED"
    COMPANY_NOT_ACCEPTING_LINE = "COMPANY_NOT_ACCEPTING_LINE"
    INVALID_REMINDER = "INVALID_REMINDER"
    MISSING_ACTIVITY_TIME = "MISSING_ACTIVITY_TIME"
    INVALID_DATETIME = "INVALID_DATETIME"
    DUPLICATE_REMINDER_ID = "DUPLICATE_REMINDER_ID"


@dataclass(frozen=True)
class ReminderDefinition:
    reminder_id: str
    enabled: bool
    interval: int
    unit: ReminderUnit | str
    message: str
    order: int = 0


@dataclass(frozen=True)
class ReminderSchedule:
    valid: bool
    reason_code: Optional[ReminderReasonCode]
    reminder_id: str
    due_at: Optional[datetime]


@dataclass(frozen=True)
class ReminderDecision:
    should_send: bool
    reason_code: ReminderReasonCode
    reminder_id: str
    due_at: Optional[datetime]
    evaluated_at: Optional[datetime]
    delay_seconds: Optional[int]
    order: int


@dataclass(frozen=True)
class ReminderBatchDecision:
    decisions: tuple[ReminderDecision, ...]
    due: tuple[ReminderDecision, ...]
    reason_code: Optional[ReminderReasonCode] = None


_UNIT_LIMITS = {
    ReminderUnit.MINUTES: 525600,
    ReminderUnit.HOURS: 8760,
    ReminderUnit.DAYS: 365,
}


def _normalize_aware_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        return None
    return value.astimezone(timezone.utc)


def _validated_unit(reminder: ReminderDefinition) -> Optional[ReminderUnit]:
    try:
        return ReminderUnit(reminder.unit)
    except (TypeError, ValueError):
        return None


def _validate_reminder(
    reminder: ReminderDefinition,
) -> Optional[ReminderReasonCode]:
    if (
        not isinstance(reminder.reminder_id, str)
        or not reminder.reminder_id.strip()
    ):
        return ReminderReasonCode.INVALID_REMINDER
    if not isinstance(reminder.enabled, bool):
        return ReminderReasonCode.INVALID_REMINDER
    if (
        not isinstance(reminder.interval, int)
        or isinstance(reminder.interval, bool)
        or reminder.interval <= 0
    ):
        return ReminderReasonCode.INVALID_REMINDER
    unit = _validated_unit(reminder)
    if unit is None or reminder.interval > _UNIT_LIMITS[unit]:
        return ReminderReasonCode.INVALID_REMINDER
    if (
        not isinstance(reminder.message, str)
        or not reminder.message.strip()
        or len(reminder.message) > MAX_MESSAGE_LENGTH
    ):
        return ReminderReasonCode.INVALID_REMINDER
    if (
        not isinstance(reminder.order, int)
        or isinstance(reminder.order, bool)
        or reminder.order < 0
    ):
        return ReminderReasonCode.INVALID_REMINDER
    return None


def calculate_due_at(
    reminder: ReminderDefinition,
    *,
    activity_at: Optional[datetime],
) -> ReminderSchedule:
    validation_reason = _validate_reminder(reminder)
    reminder_id = (
        reminder.reminder_id
        if isinstance(reminder.reminder_id, str)
        else ""
    )
    if validation_reason is not None:
        return ReminderSchedule(
            False,
            validation_reason,
            reminder_id,
            None,
        )
    if activity_at is None:
        return ReminderSchedule(
            False,
            ReminderReasonCode.MISSING_ACTIVITY_TIME,
            reminder_id,
            None,
        )
    normalized_activity = _normalize_aware_datetime(activity_at)
    if normalized_activity is None:
        return ReminderSchedule(
            False,
            ReminderReasonCode.INVALID_DATETIME,
            reminder_id,
            None,
        )

    unit = ReminderUnit(reminder.unit)
    if unit is ReminderUnit.MINUTES:
        delay = timedelta(minutes=reminder.interval)
    elif unit is ReminderUnit.HOURS:
        delay = timedelta(hours=reminder.interval)
    else:
        delay = timedelta(days=reminder.interval)
    return ReminderSchedule(
        True,
        None,
        reminder_id,
        normalized_activity + delay,
    )


def _safe_order(reminder: ReminderDefinition) -> int:
    if (
        isinstance(reminder.order, int)
        and not isinstance(reminder.order, bool)
        and reminder.order >= 0
    ):
        return reminder.order
    return 0


def _decision(
    reminder: ReminderDefinition,
    reason_code: ReminderReasonCode,
    *,
    should_send: bool = False,
    due_at: Optional[datetime] = None,
    evaluated_at: Optional[datetime] = None,
) -> ReminderDecision:
    delay_seconds = (
        int((evaluated_at - due_at).total_seconds())
        if evaluated_at is not None and due_at is not None
        else None
    )
    return ReminderDecision(
        should_send=should_send,
        reason_code=reason_code,
        reminder_id=(
            reminder.reminder_id
            if isinstance(reminder.reminder_id, str)
            else ""
        ),
        due_at=due_at,
        evaluated_at=evaluated_at,
        delay_seconds=delay_seconds,
        order=_safe_order(reminder),
    )


def _decision_from_schedule(
    reminder: ReminderDefinition,
    schedule: ReminderSchedule,
    reason_code: ReminderReasonCode,
    evaluated_at: datetime,
    *,
    should_send: bool = False,
) -> ReminderDecision:
    return _decision(
        reminder,
        reason_code,
        should_send=should_send,
        due_at=schedule.due_at,
        evaluated_at=evaluated_at,
    )


def _company_accepts_line(
    company_state: CompanyState | str,
) -> bool:
    try:
        state = CompanyState(company_state)
    except (TypeError, ValueError):
        return False
    return evaluate_company_capability(
        state,
        CompanyCapability.LINE_ACCEPT,
    ).allowed


def evaluate_reminder(
    reminder: ReminderDefinition,
    *,
    activity_at: Optional[datetime],
    now: datetime,
    session_status: str,
    sent_reminder_ids: Collection[str],
    application_reception_enabled: bool,
    company_state: CompanyState | str,
) -> ReminderDecision:
    normalized_now = _normalize_aware_datetime(now)
    if normalized_now is None:
        return _decision(
            reminder,
            ReminderReasonCode.INVALID_DATETIME,
        )

    schedule = calculate_due_at(reminder, activity_at=activity_at)
    if not schedule.valid:
        return _decision(
            reminder,
            schedule.reason_code or ReminderReasonCode.INVALID_REMINDER,
            evaluated_at=normalized_now,
        )
    if not reminder.enabled:
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.REMINDER_DISABLED,
            normalized_now,
        )
    if session_status == "completed":
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.SESSION_COMPLETED,
            normalized_now,
        )
    if session_status != "active":
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.SESSION_NOT_ACTIVE,
            normalized_now,
        )
    if application_reception_enabled is not True:
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.APPLICATION_RECEPTION_DISABLED,
            normalized_now,
        )
    if not _company_accepts_line(company_state):
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            normalized_now,
        )
    if reminder.reminder_id in sent_reminder_ids:
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.ALREADY_SENT,
            normalized_now,
        )
    if normalized_now < schedule.due_at:
        return _decision_from_schedule(
            reminder,
            schedule,
            ReminderReasonCode.NOT_DUE,
            normalized_now,
        )
    return _decision_from_schedule(
        reminder,
        schedule,
        ReminderReasonCode.DUE,
        normalized_now,
        should_send=True,
    )


def _decision_sort_key(
    decision: ReminderDecision,
) -> tuple[bool, datetime, int, str, str]:
    return (
        decision.due_at is None,
        decision.due_at or datetime.max.replace(tzinfo=timezone.utc),
        decision.order,
        decision.reminder_id,
        decision.reason_code.value,
    )


def evaluate_reminders(
    reminders: Collection[ReminderDefinition],
    *,
    activity_at: Optional[datetime],
    now: datetime,
    session_status: str,
    sent_reminder_ids: Collection[str],
    application_reception_enabled: bool,
    company_state: CompanyState | str,
) -> ReminderBatchDecision:
    definitions = tuple(reminders)
    normalized_now = _normalize_aware_datetime(now)
    if len(definitions) > MAX_REMINDERS:
        decisions = tuple(
            _decision(
                item,
                ReminderReasonCode.INVALID_REMINDER,
                evaluated_at=normalized_now,
            )
            for item in definitions
        )
        return ReminderBatchDecision(
            decisions=tuple(sorted(decisions, key=_decision_sort_key)),
            due=(),
            reason_code=ReminderReasonCode.INVALID_REMINDER,
        )

    id_counts = Counter(
        item.reminder_id
        for item in definitions
        if isinstance(item.reminder_id, str) and item.reminder_id.strip()
    )
    decisions: list[ReminderDecision] = []
    for item in definitions:
        if (
            isinstance(item.reminder_id, str)
            and item.reminder_id.strip()
            and id_counts[item.reminder_id] > 1
        ):
            decisions.append(
                _decision(
                    item,
                    ReminderReasonCode.DUPLICATE_REMINDER_ID,
                    evaluated_at=normalized_now,
                )
            )
            continue
        decisions.append(
            evaluate_reminder(
                item,
                activity_at=activity_at,
                now=now,
                session_status=session_status,
                sent_reminder_ids=sent_reminder_ids,
                application_reception_enabled=application_reception_enabled,
                company_state=company_state,
            )
        )

    ordered_decisions = tuple(sorted(decisions, key=_decision_sort_key))
    due = tuple(
        sorted(
            (
                decision
                for decision in ordered_decisions
                if decision.should_send
            ),
            key=_decision_sort_key,
        )[:1]
    )
    return ReminderBatchDecision(
        decisions=ordered_decisions,
        due=due,
        reason_code=None,
    )
