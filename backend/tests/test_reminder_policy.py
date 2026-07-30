from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from authz_policy import CompanyState
from reminder_policy import (
    MAX_REMINDERS,
    ReminderBatchDecision,
    ReminderDecision,
    ReminderDefinition,
    ReminderReasonCode,
    ReminderSchedule,
    ReminderUnit,
    calculate_due_at,
    evaluate_reminder,
    evaluate_reminders,
)


UTC = timezone.utc
JST = timezone(timedelta(hours=9))
ACTIVITY_AT = datetime(2026, 7, 30, 0, 0, 0, tzinfo=UTC)


def reminder(**overrides: object) -> ReminderDefinition:
    values: dict[str, object] = {
        "reminder_id": "reminder-1",
        "enabled": True,
        "interval": 1,
        "unit": ReminderUnit.HOURS,
        "message": "応募の続きから入力できます。",
        "order": 0,
    }
    values.update(overrides)
    return ReminderDefinition(**values)  # type: ignore[arg-type]


def evaluate(
    definition: ReminderDefinition | None = None,
    **overrides: object,
) -> ReminderDecision:
    values: dict[str, object] = {
        "activity_at": ACTIVITY_AT,
        "now": ACTIVITY_AT + timedelta(hours=1),
        "session_status": "active",
        "sent_reminder_ids": frozenset(),
        "application_reception_enabled": True,
        "company_state": CompanyState.ACTIVE,
    }
    values.update(overrides)
    return evaluate_reminder(
        definition or reminder(),
        **values,  # type: ignore[arg-type]
    )


def evaluate_batch(
    definitions: tuple[ReminderDefinition, ...],
    **overrides: object,
) -> ReminderBatchDecision:
    values: dict[str, object] = {
        "activity_at": ACTIVITY_AT,
        "now": ACTIVITY_AT + timedelta(days=30),
        "session_status": "active",
        "sent_reminder_ids": frozenset(),
        "application_reception_enabled": True,
        "company_state": CompanyState.ACTIVE,
    }
    values.update(overrides)
    return evaluate_reminders(
        definitions,
        **values,  # type: ignore[arg-type]
    )


class ReminderScheduleTests(unittest.TestCase):
    def assert_invalid(
        self,
        definition: ReminderDefinition,
        reason_code: ReminderReasonCode,
        *,
        activity_at: datetime | None = ACTIVITY_AT,
    ) -> ReminderSchedule:
        result = calculate_due_at(definition, activity_at=activity_at)
        self.assertFalse(result.valid)
        self.assertEqual(reason_code, result.reason_code)
        self.assertIsNone(result.due_at)
        return result

    def test_minutes_are_added_to_activity_time(self) -> None:
        result = calculate_due_at(
            reminder(interval=30, unit=ReminderUnit.MINUTES),
            activity_at=ACTIVITY_AT,
        )
        self.assertEqual(ACTIVITY_AT + timedelta(minutes=30), result.due_at)

    def test_hours_are_added_to_activity_time(self) -> None:
        result = calculate_due_at(
            reminder(interval=24, unit=ReminderUnit.HOURS),
            activity_at=ACTIVITY_AT,
        )
        self.assertEqual(ACTIVITY_AT + timedelta(hours=24), result.due_at)

    def test_days_are_added_to_activity_time(self) -> None:
        result = calculate_due_at(
            reminder(interval=3, unit=ReminderUnit.DAYS),
            activity_at=ACTIVITY_AT,
        )
        self.assertEqual(ACTIVITY_AT + timedelta(days=3), result.due_at)

    def test_non_utc_aware_activity_is_normalized_to_utc(self) -> None:
        activity_jst = ACTIVITY_AT.astimezone(JST)
        result = calculate_due_at(
            reminder(interval=1, unit=ReminderUnit.HOURS),
            activity_at=activity_jst,
        )
        self.assertEqual(ACTIVITY_AT + timedelta(hours=1), result.due_at)
        self.assertEqual(UTC, result.due_at.tzinfo)

    def test_naive_activity_is_rejected(self) -> None:
        self.assert_invalid(
            reminder(),
            ReminderReasonCode.INVALID_DATETIME,
            activity_at=ACTIVITY_AT.replace(tzinfo=None),
        )

    def test_non_datetime_activity_is_rejected(self) -> None:
        result = calculate_due_at(
            reminder(),
            activity_at="2026-07-30T00:00:00Z",  # type: ignore[arg-type]
        )
        self.assertFalse(result.valid)
        self.assertEqual(ReminderReasonCode.INVALID_DATETIME, result.reason_code)

    def test_missing_activity_is_rejected(self) -> None:
        self.assert_invalid(
            reminder(),
            ReminderReasonCode.MISSING_ACTIVITY_TIME,
            activity_at=None,
        )

    def test_disabled_reminder_still_has_a_calculable_schedule(self) -> None:
        result = calculate_due_at(
            reminder(enabled=False),
            activity_at=ACTIVITY_AT,
        )
        self.assertTrue(result.valid)
        self.assertEqual(ACTIVITY_AT + timedelta(hours=1), result.due_at)


class ReminderValidationTests(unittest.TestCase):
    def assert_invalid(self, definition: ReminderDefinition) -> None:
        result = calculate_due_at(definition, activity_at=ACTIVITY_AT)
        self.assertFalse(result.valid)
        self.assertEqual(ReminderReasonCode.INVALID_REMINDER, result.reason_code)
        self.assertIsNone(result.due_at)

    def test_empty_reminder_id_is_invalid(self) -> None:
        self.assert_invalid(reminder(reminder_id=""))

    def test_whitespace_reminder_id_is_invalid(self) -> None:
        self.assert_invalid(reminder(reminder_id="   "))

    def test_non_string_reminder_id_is_invalid(self) -> None:
        self.assert_invalid(reminder(reminder_id=123))

    def test_enabled_must_be_boolean(self) -> None:
        self.assert_invalid(reminder(enabled="true"))

    def test_zero_interval_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=0))

    def test_negative_interval_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=-1))

    def test_boolean_interval_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=True))

    def test_fractional_interval_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=1.5))

    def test_unsupported_unit_is_invalid(self) -> None:
        self.assert_invalid(reminder(unit="weeks"))

    def test_empty_message_is_invalid(self) -> None:
        self.assert_invalid(reminder(message=""))

    def test_whitespace_message_is_invalid(self) -> None:
        self.assert_invalid(reminder(message=" \n "))

    def test_non_string_message_is_invalid(self) -> None:
        self.assert_invalid(reminder(message=123))

    def test_5000_character_message_is_valid(self) -> None:
        result = calculate_due_at(
            reminder(message="a" * 5000),
            activity_at=ACTIVITY_AT,
        )
        self.assertTrue(result.valid)

    def test_5001_character_message_is_invalid(self) -> None:
        self.assert_invalid(reminder(message="a" * 5001))

    def test_maximum_minutes_interval_is_valid(self) -> None:
        result = calculate_due_at(
            reminder(interval=525600, unit=ReminderUnit.MINUTES),
            activity_at=ACTIVITY_AT,
        )
        self.assertTrue(result.valid)

    def test_minutes_interval_above_maximum_is_invalid(self) -> None:
        self.assert_invalid(
            reminder(interval=525601, unit=ReminderUnit.MINUTES)
        )

    def test_maximum_hours_interval_is_valid(self) -> None:
        result = calculate_due_at(
            reminder(interval=8760, unit=ReminderUnit.HOURS),
            activity_at=ACTIVITY_AT,
        )
        self.assertTrue(result.valid)

    def test_hours_interval_above_maximum_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=8761, unit=ReminderUnit.HOURS))

    def test_maximum_days_interval_is_valid(self) -> None:
        result = calculate_due_at(
            reminder(interval=365, unit=ReminderUnit.DAYS),
            activity_at=ACTIVITY_AT,
        )
        self.assertTrue(result.valid)

    def test_days_interval_above_maximum_is_invalid(self) -> None:
        self.assert_invalid(reminder(interval=366, unit=ReminderUnit.DAYS))

    def test_negative_order_is_invalid(self) -> None:
        self.assert_invalid(reminder(order=-1))

    def test_boolean_order_is_invalid(self) -> None:
        self.assert_invalid(reminder(order=True))

    def test_non_integer_order_is_invalid(self) -> None:
        self.assert_invalid(reminder(order="first"))


class ReminderEvaluationTests(unittest.TestCase):
    def assert_rejected(
        self,
        reason_code: ReminderReasonCode,
        definition: ReminderDefinition | None = None,
        **overrides: object,
    ) -> ReminderDecision:
        result = evaluate(definition, **overrides)
        self.assertFalse(result.should_send)
        self.assertEqual(reason_code, result.reason_code)
        return result

    def test_one_second_before_due_is_not_due(self) -> None:
        result = evaluate(now=ACTIVITY_AT + timedelta(hours=1, seconds=-1))
        self.assertFalse(result.should_send)
        self.assertEqual(ReminderReasonCode.NOT_DUE, result.reason_code)
        self.assertEqual(-1, result.delay_seconds)

    def test_exactly_due_is_sendable(self) -> None:
        result = evaluate(now=ACTIVITY_AT + timedelta(hours=1))
        self.assertTrue(result.should_send)
        self.assertEqual(ReminderReasonCode.DUE, result.reason_code)
        self.assertEqual(0, result.delay_seconds)

    def test_one_second_after_due_is_sendable(self) -> None:
        result = evaluate(now=ACTIVITY_AT + timedelta(hours=1, seconds=1))
        self.assertTrue(result.should_send)
        self.assertEqual(ReminderReasonCode.DUE, result.reason_code)
        self.assertEqual(1, result.delay_seconds)

    def test_now_before_activity_is_not_due(self) -> None:
        result = evaluate(now=ACTIVITY_AT - timedelta(seconds=1))
        self.assertFalse(result.should_send)
        self.assertEqual(ReminderReasonCode.NOT_DUE, result.reason_code)

    def test_utc_aware_now_is_accepted(self) -> None:
        result = evaluate(now=ACTIVITY_AT + timedelta(hours=1))
        self.assertEqual(ACTIVITY_AT + timedelta(hours=1), result.evaluated_at)

    def test_non_utc_aware_now_is_normalized_to_utc(self) -> None:
        due_jst = (ACTIVITY_AT + timedelta(hours=1)).astimezone(JST)
        result = evaluate(now=due_jst)
        self.assertTrue(result.should_send)
        self.assertEqual(UTC, result.evaluated_at.tzinfo)

    def test_naive_now_is_rejected(self) -> None:
        result = self.assert_rejected(
            ReminderReasonCode.INVALID_DATETIME,
            now=(ACTIVITY_AT + timedelta(hours=1)).replace(tzinfo=None),
        )
        self.assertIsNone(result.evaluated_at)

    def test_non_datetime_now_is_rejected(self) -> None:
        result = self.assert_rejected(
            ReminderReasonCode.INVALID_DATETIME,
            now="2026-07-30T01:00:00Z",
        )
        self.assertIsNone(result.evaluated_at)

    def test_active_session_is_sendable(self) -> None:
        self.assertTrue(evaluate(session_status="active").should_send)

    def test_completed_session_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.SESSION_COMPLETED,
            session_status="completed",
        )

    def test_cancelled_session_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.SESSION_NOT_ACTIVE,
            session_status="cancelled",
        )

    def test_unknown_session_status_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.SESSION_NOT_ACTIVE,
            session_status="paused",
        )

    def test_uppercase_session_status_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.SESSION_NOT_ACTIVE,
            session_status="ACTIVE",
        )

    def test_empty_session_status_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.SESSION_NOT_ACTIVE,
            session_status="",
        )

    def test_disabled_reminder_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.REMINDER_DISABLED,
            reminder(enabled=False),
        )

    def test_application_reception_enabled_is_sendable(self) -> None:
        self.assertTrue(
            evaluate(application_reception_enabled=True).should_send
        )

    def test_application_reception_disabled_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.APPLICATION_RECEPTION_DISABLED,
            application_reception_enabled=False,
        )

    def test_non_boolean_application_reception_fails_closed(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.APPLICATION_RECEPTION_DISABLED,
            application_reception_enabled="yes",
        )

    def test_monitor_active_company_is_sendable(self) -> None:
        self.assertTrue(
            evaluate(company_state=CompanyState.MONITOR_ACTIVE).should_send
        )

    def test_active_company_is_sendable(self) -> None:
        self.assertTrue(evaluate(company_state=CompanyState.ACTIVE).should_send)

    def test_monitor_expired_company_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            company_state=CompanyState.MONITOR_EXPIRED,
        )

    def test_suspended_company_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            company_state=CompanyState.SUSPENDED,
        )

    def test_closed_company_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            company_state=CompanyState.CLOSED,
        )

    def test_unknown_company_status_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            company_state="unknown",
        )

    def test_uppercase_company_status_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.COMPANY_NOT_ACCEPTING_LINE,
            company_state="ACTIVE",
        )

    def test_unsent_reminder_is_sendable(self) -> None:
        self.assertTrue(evaluate(sent_reminder_ids=frozenset()).should_send)

    def test_sent_reminder_is_not_sendable(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.ALREADY_SENT,
            sent_reminder_ids={"reminder-1"},
        )

    def test_different_sent_reminder_does_not_block(self) -> None:
        self.assertTrue(
            evaluate(sent_reminder_ids={"other-reminder"}).should_send
        )

    def test_duplicate_history_entries_still_block(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.ALREADY_SENT,
            sent_reminder_ids=("reminder-1", "reminder-1"),
        )

    def test_history_order_does_not_change_result(self) -> None:
        first = evaluate(sent_reminder_ids=("other", "reminder-1"))
        second = evaluate(sent_reminder_ids=("reminder-1", "other"))
        self.assertEqual(first, second)

    def test_invalid_reminder_returns_structured_rejection(self) -> None:
        result = self.assert_rejected(
            ReminderReasonCode.INVALID_REMINDER,
            reminder(interval=0),
        )
        self.assertEqual("reminder-1", result.reminder_id)

    def test_missing_activity_returns_structured_rejection(self) -> None:
        self.assert_rejected(
            ReminderReasonCode.MISSING_ACTIVITY_TIME,
            activity_at=None,
        )

    def test_reason_code_does_not_contain_message_text(self) -> None:
        private_message = "candidate@example.invalid"
        result = evaluate(reminder(message=private_message))
        self.assertNotIn(private_message, result.reason_code.value)


class ReminderBatchTests(unittest.TestCase):
    def test_empty_definitions_return_empty_batch(self) -> None:
        result = evaluate_batch(())
        self.assertEqual((), result.decisions)
        self.assertEqual((), result.due)
        self.assertIsNone(result.reason_code)

    def test_single_due_definition_is_selected(self) -> None:
        result = evaluate_batch((reminder(),))
        self.assertEqual(("reminder-1",), tuple(item.reminder_id for item in result.due))

    def test_single_future_definition_is_not_selected(self) -> None:
        result = evaluate_batch(
            (reminder(interval=31, unit=ReminderUnit.DAYS),)
        )
        self.assertEqual((), result.due)

    def test_all_definitions_are_evaluated(self) -> None:
        definitions = (
            reminder(reminder_id="one", interval=1),
            reminder(reminder_id="two", interval=2),
            reminder(reminder_id="three", interval=3),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(3, len(result.decisions))

    def test_multiple_overdue_definitions_select_oldest_due_only(self) -> None:
        definitions = (
            reminder(reminder_id="24h", interval=24),
            reminder(reminder_id="1h", interval=1),
            reminder(reminder_id="3h", interval=3),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(("1h",), tuple(item.reminder_id for item in result.due))

    def test_next_oldest_is_selected_after_oldest_was_sent(self) -> None:
        definitions = (
            reminder(reminder_id="1h", interval=1),
            reminder(reminder_id="3h", interval=3),
            reminder(reminder_id="24h", interval=24),
        )
        result = evaluate_batch(
            definitions,
            sent_reminder_ids={"1h"},
        )
        self.assertEqual(("3h",), tuple(item.reminder_id for item in result.due))

    def test_input_order_does_not_change_selected_reminder(self) -> None:
        early = reminder(reminder_id="early", interval=1)
        late = reminder(reminder_id="late", interval=24)
        first = evaluate_batch((late, early))
        second = evaluate_batch((early, late))
        self.assertEqual(first.due, second.due)

    def test_same_due_time_uses_explicit_order(self) -> None:
        definitions = (
            reminder(reminder_id="second", order=2),
            reminder(reminder_id="first", order=1),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(("first",), tuple(item.reminder_id for item in result.due))

    def test_same_due_time_and_order_use_reminder_id(self) -> None:
        definitions = (
            reminder(reminder_id="z-reminder", order=1),
            reminder(reminder_id="a-reminder", order=1),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(
            ("a-reminder",),
            tuple(item.reminder_id for item in result.due),
        )

    def test_invalid_definition_does_not_block_valid_definition(self) -> None:
        definitions = (
            reminder(reminder_id="invalid", interval=0),
            reminder(reminder_id="valid", interval=1),
        )
        result = evaluate_batch(definitions)
        reasons = {item.reminder_id: item.reason_code for item in result.decisions}
        self.assertEqual(ReminderReasonCode.INVALID_REMINDER, reasons["invalid"])
        self.assertEqual(("valid",), tuple(item.reminder_id for item in result.due))

    def test_disabled_definition_does_not_block_valid_definition(self) -> None:
        definitions = (
            reminder(reminder_id="disabled", enabled=False, interval=1),
            reminder(reminder_id="valid", interval=2),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(("valid",), tuple(item.reminder_id for item in result.due))

    def test_duplicate_definition_ids_are_all_rejected(self) -> None:
        definitions = (
            reminder(reminder_id="duplicate", interval=1),
            reminder(reminder_id="duplicate", interval=2),
        )
        result = evaluate_batch(definitions)
        self.assertEqual((), result.due)
        self.assertEqual(
            [ReminderReasonCode.DUPLICATE_REMINDER_ID] * 2,
            [item.reason_code for item in result.decisions],
        )

    def test_duplicate_ids_do_not_block_different_valid_id(self) -> None:
        definitions = (
            reminder(reminder_id="duplicate", interval=1),
            reminder(reminder_id="valid", interval=2),
            reminder(reminder_id="duplicate", interval=3),
        )
        result = evaluate_batch(definitions)
        self.assertEqual(("valid",), tuple(item.reminder_id for item in result.due))

    def test_duplicate_id_result_is_independent_of_input_order(self) -> None:
        first = reminder(reminder_id="duplicate", interval=1)
        second = reminder(reminder_id="duplicate", interval=2)
        left = evaluate_batch((first, second))
        right = evaluate_batch((second, first))
        self.assertEqual(
            sorted(item.reason_code.value for item in left.decisions),
            sorted(item.reason_code.value for item in right.decisions),
        )

    def test_maximum_definition_count_is_accepted(self) -> None:
        definitions = tuple(
            reminder(
                reminder_id=f"reminder-{index:02d}",
                interval=index,
                unit=ReminderUnit.HOURS,
                order=index,
            )
            for index in range(1, MAX_REMINDERS + 1)
        )
        result = evaluate_batch(definitions)
        self.assertIsNone(result.reason_code)
        self.assertEqual(MAX_REMINDERS, len(result.decisions))

    def test_definition_count_above_maximum_is_rejected(self) -> None:
        definitions = tuple(
            reminder(
                reminder_id=f"reminder-{index:02d}",
                interval=index,
                unit=ReminderUnit.HOURS,
                order=index,
            )
            for index in range(1, MAX_REMINDERS + 2)
        )
        result = evaluate_batch(definitions)
        self.assertEqual(ReminderReasonCode.INVALID_REMINDER, result.reason_code)
        self.assertEqual((), result.due)
        self.assertTrue(
            all(
                item.reason_code is ReminderReasonCode.INVALID_REMINDER
                for item in result.decisions
            )
        )

    def test_sent_history_order_does_not_change_batch_selection(self) -> None:
        definitions = (
            reminder(reminder_id="one", interval=1),
            reminder(reminder_id="two", interval=2),
            reminder(reminder_id="three", interval=3),
        )
        first = evaluate_batch(
            definitions,
            sent_reminder_ids=("one", "two"),
        )
        second = evaluate_batch(
            definitions,
            sent_reminder_ids=("two", "one"),
        )
        self.assertEqual(first.due, second.due)

    def test_batch_never_selects_same_reminder_id_twice(self) -> None:
        definitions = (
            reminder(reminder_id="one", interval=1),
            reminder(reminder_id="two", interval=2),
        )
        result = evaluate_batch(definitions)
        selected_ids = [item.reminder_id for item in result.due]
        self.assertEqual(len(selected_ids), len(set(selected_ids)))
        self.assertLessEqual(len(selected_ids), 1)


if __name__ == "__main__":
    unittest.main()
