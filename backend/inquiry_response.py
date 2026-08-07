from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from line_send_validation import validate_line_message_text


class InquiryStatus(str, Enum):
    UNANSWERED = "未対応"
    IN_PROGRESS = "対応中"
    COMPLETED = "対応済み"


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
