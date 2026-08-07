from dataclasses import dataclass
from enum import Enum
import re


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
