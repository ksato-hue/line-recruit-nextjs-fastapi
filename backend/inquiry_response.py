import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from line_send_validation import validate_line_message_text


class InquiryStatus(str, Enum):
    UNANSWERED = "未対応"
    IN_PROGRESS = "対応中"
    COMPLETED = "対応済み"


class InquirySort(str, Enum):
    OLDEST = "oldest"
    NEWEST = "newest"


class InquiryDeliveryStatus(str, Enum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERY_UNKNOWN = "delivery_unknown"


class InquiryReasonCode(str, Enum):
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"


@dataclass(frozen=True)
class InquiryPolicyDecision:
    allowed: bool
    reason_code: InquiryReasonCode | None = None


@dataclass(frozen=True)
class InquiryCursor:
    created_at: datetime
    inquiry_id: UUID


INQUIRY_MESSAGE_PREVIEW_LENGTH = 160
_CANONICAL_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")


def _parse_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed


def encode_inquiry_cursor(created_at: object, inquiry_id: object) -> str:
    parsed_created_at = _parse_aware_datetime(created_at, "created_at")
    try:
        parsed_id = UUID(str(inquiry_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("id must be a UUID") from exc
    payload = json.dumps(
        {
            "created_at": parsed_created_at.isoformat(),
            "id": str(parsed_id),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict:
    payload = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("cursor contains a duplicate JSON key")
        payload[key] = value
    return payload


def decode_inquiry_cursor(token: str) -> InquiryCursor:
    if not isinstance(token, str) or not token:
        raise ValueError("cursor must be a non-empty string")
    if _CANONICAL_BASE64URL.fullmatch(token) is None:
        raise ValueError("cursor must use unpadded base64url")
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.b64decode(
            token + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(
            decoded.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cursor is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {"created_at", "id"}:
        raise ValueError("cursor has invalid fields")
    created_at = _parse_aware_datetime(payload["created_at"], "created_at")
    try:
        inquiry_id = UUID(payload["id"])
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError("id must be a UUID") from exc
    cursor = InquiryCursor(created_at=created_at, inquiry_id=inquiry_id)
    if token != encode_inquiry_cursor(cursor.created_at.isoformat(), cursor.inquiry_id):
        raise ValueError("cursor is not canonical")
    return cursor


def inquiry_cursor_filter(cursor: InquiryCursor, sort: InquirySort) -> str:
    operator = "gt" if sort == InquirySort.OLDEST else "lt"
    created_at = cursor.created_at.isoformat()
    inquiry_id = str(cursor.inquiry_id)
    return (
        f"created_at.{operator}.{created_at},"
        f"and(created_at.eq.{created_at},id.{operator}.{inquiry_id})"
    )


def inquiry_summary(
    row: dict,
    *,
    related_applicant_exists: bool,
    now: datetime,
) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    message = row.get("message")
    message_preview = message[:INQUIRY_MESSAGE_PREVIEW_LENGTH] if isinstance(message, str) else ""
    unanswered_age_seconds = None
    if row.get("status") == InquiryStatus.UNANSWERED.value:
        created_at = _parse_aware_datetime(row.get("created_at"), "created_at")
        unanswered_age_seconds = max(
            int((now.astimezone(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()),
            0,
        )
    return {
        "id": row.get("id"),
        "message_preview": message_preview,
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "assignee_name": row.get("assignee_name"),
        "last_replied_at": row.get("last_replied_at"),
        "updated_at": row.get("updated_at"),
        "related_applicant_exists": bool(related_applicant_exists),
        "unanswered_age_seconds": unanswered_age_seconds,
    }


def safe_inquiry_detail(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "message": row.get("message"),
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "assignee_name": row.get("assignee_name"),
        "last_replied_at": row.get("last_replied_at"),
        "updated_at": row.get("updated_at"),
    }


def extract_default_assignee_name(value: str | None) -> str:
    if value is None:
        return ""
    stripped = value.strip(" \u3000")
    if not stripped:
        return ""
    return re.split(r"[ \u3000]+", stripped)[0]


def normalize_assignee_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("assignee name must be a string")
    normalized = value.strip(" \u3000")
    if not normalized or len(normalized) > 80:
        raise ValueError("assignee name must contain 1 to 80 characters")
    return normalized


def validate_timezone_aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("expected_updated_at must include a timezone")
    return value


class InquiryUpdateRequest(BaseModel):
    """Browser request contract for an inquiry status or assignee update."""

    model_config = ConfigDict(extra="forbid")

    status: InquiryStatus | None = None
    assignee_name: StrictStr | None = None
    expected_updated_at: datetime

    @field_validator("assignee_name")
    @classmethod
    def validate_assignee_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_assignee_name(value)

    @field_validator("expected_updated_at")
    @classmethod
    def validate_expected_updated_at(cls, value: datetime) -> datetime:
        return validate_timezone_aware_datetime(value)

    @model_validator(mode="after")
    def require_mutable_field(self) -> "InquiryUpdateRequest":
        if self.status is None and self.assignee_name is None:
            raise ValueError("status or assignee_name is required")
        return self


class InquiryReplyRequest(BaseModel):
    """Browser request contract for sending an inquiry reply."""

    model_config = ConfigDict(extra="forbid")

    assignee_name: StrictStr
    message: StrictStr
    idempotency_key: UUID
    expected_updated_at: datetime

    @field_validator("assignee_name")
    @classmethod
    def validate_assignee_name(cls, value: str) -> str:
        return normalize_assignee_name(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return validate_line_message_text(value)

    @field_validator("expected_updated_at")
    @classmethod
    def validate_expected_updated_at(cls, value: datetime) -> datetime:
        return validate_timezone_aware_datetime(value)


def validate_operator_status_transition(
    current: str | InquiryStatus,
    target: str | InquiryStatus,
) -> InquiryPolicyDecision:
    try:
        current_status = InquiryStatus(current)
        target_status = InquiryStatus(target)
    except ValueError:
        return InquiryPolicyDecision(False, InquiryReasonCode.INVALID_STATUS_TRANSITION)

    if current_status == target_status:
        return InquiryPolicyDecision(True)
    if (current_status, target_status) in {
        (InquiryStatus.UNANSWERED, InquiryStatus.IN_PROGRESS),
        (InquiryStatus.COMPLETED, InquiryStatus.IN_PROGRESS),
    }:
        return InquiryPolicyDecision(True)
    return InquiryPolicyDecision(False, InquiryReasonCode.INVALID_STATUS_TRANSITION)


def mask_line_destination(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 5:
        return "…"
    prefix_length = min(5, len(value) - 5)
    return f"{value[:prefix_length]}…{value[-4:]}"
