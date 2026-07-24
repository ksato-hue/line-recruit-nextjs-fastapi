from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    PLATFORM_ADMIN = "platform_admin"


class TenantOperation(str, Enum):
    APPLICANT_READ = "applicant_read"
    APPLICANT_UPDATE = "applicant_update"
    MESSAGE_SEND = "message_send"
    INTERVIEW_MANAGE = "interview_manage"
    SETTINGS_READ = "settings_read"
    SETTINGS_UPDATE = "settings_update"
    MEMBER_READ = "member_read"
    MEMBER_INVITE = "member_invite"
    MEMBER_SUSPEND = "member_suspend"
    MEMBER_ROLE_UPDATE = "member_role_update"
    CSV_EXPORT = "csv_export"


class PlatformOperation(str, Enum):
    COMPANY_METADATA_READ = "company_metadata_read"
    INITIAL_OWNER_INVITE = "initial_owner_invite"
    MFA_RESET = "mfa_reset"
    OWNER_CHANGE = "owner_change"
    COMPANY_STATUS_UPDATE = "company_status_update"
    AUDIT_LOG_READ = "audit_log_read"


class CompanyState(str, Enum):
    MONITOR_ACTIVE = "monitor_active"
    MONITOR_EXPIRED = "monitor_expired"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class CompanyCapability(str, Enum):
    DASHBOARD_READ = "dashboard_read"
    DASHBOARD_WRITE = "dashboard_write"
    LINE_ACCEPT = "line_accept"
    CSV_EXPORT = "csv_export"


class MembershipStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class AssuranceLevel(str, Enum):
    AAL1 = "aal1"
    AAL2 = "aal2"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ReasonCode(str, Enum):
    MFA_REQUIRED = "MFA_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    SESSION_INVALID = "SESSION_INVALID"
    MEMBERSHIP_NOT_ACTIVE = "MEMBERSHIP_NOT_ACTIVE"
    COMPANY_READ_ONLY = "COMPANY_READ_ONLY"
    COMPANY_SUSPENDED = "COMPANY_SUSPENDED"
    INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"
    INVITATION_EXPIRED = "INVITATION_EXPIRED"
    INVITATION_INVALID = "INVITATION_INVALID"
    EMAIL_MISMATCH = "EMAIL_MISMATCH"
    OWNER_CHANGE_FORBIDDEN = "OWNER_CHANGE_FORBIDDEN"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: Optional[ReasonCode] = None


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    user_id: str
    absolute_expires_at: datetime
    revoked_at: Optional[datetime] = None


@dataclass(frozen=True)
class InvitationRecord:
    status: InvitationStatus
    email_normalized: str
    expires_at: datetime


_ALLOWED = PolicyDecision(True, None)

_ROLE_PERMISSIONS = {
    Role.OWNER: frozenset(TenantOperation),
    Role.ADMIN: frozenset(
        {
            TenantOperation.APPLICANT_READ,
            TenantOperation.APPLICANT_UPDATE,
            TenantOperation.MESSAGE_SEND,
            TenantOperation.INTERVIEW_MANAGE,
            TenantOperation.SETTINGS_READ,
            TenantOperation.SETTINGS_UPDATE,
        }
    ),
    Role.MEMBER: frozenset(
        {
            TenantOperation.APPLICANT_READ,
            TenantOperation.APPLICANT_UPDATE,
            TenantOperation.MESSAGE_SEND,
            TenantOperation.INTERVIEW_MANAGE,
            TenantOperation.SETTINGS_READ,
        }
    ),
    Role.PLATFORM_ADMIN: frozenset(),
}

_TENANT_OPERATION_CAPABILITIES = {
    TenantOperation.APPLICANT_READ: CompanyCapability.DASHBOARD_READ,
    TenantOperation.APPLICANT_UPDATE: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.MESSAGE_SEND: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.INTERVIEW_MANAGE: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.SETTINGS_READ: CompanyCapability.DASHBOARD_READ,
    TenantOperation.SETTINGS_UPDATE: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.MEMBER_READ: CompanyCapability.DASHBOARD_READ,
    TenantOperation.MEMBER_INVITE: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.MEMBER_SUSPEND: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.MEMBER_ROLE_UPDATE: CompanyCapability.DASHBOARD_WRITE,
    TenantOperation.CSV_EXPORT: CompanyCapability.CSV_EXPORT,
}

_FULL_ACCESS_COMPANY_STATES = frozenset(
    {
        CompanyState.MONITOR_ACTIVE,
        CompanyState.ACTIVE,
    }
)
_READ_ONLY_COMPANY_STATES = frozenset(
    {
        CompanyState.MONITOR_EXPIRED,
    }
)
_READ_ONLY_CAPABILITIES = frozenset(
    {
        CompanyCapability.DASHBOARD_READ,
        CompanyCapability.CSV_EXPORT,
    }
)


def _denied(reason_code: ReasonCode) -> PolicyDecision:
    return PolicyDecision(False, reason_code)


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be UTC and timezone-aware")


def evaluate_assurance_level(level: AssuranceLevel) -> PolicyDecision:
    if level is AssuranceLevel.AAL2:
        return _ALLOWED
    return _denied(ReasonCode.MFA_REQUIRED)


def evaluate_membership(status: MembershipStatus) -> PolicyDecision:
    if status is MembershipStatus.ACTIVE:
        return _ALLOWED
    return _denied(ReasonCode.MEMBERSHIP_NOT_ACTIVE)


def evaluate_company_capability(
    state: CompanyState,
    capability: CompanyCapability,
    *,
    now: Optional[datetime] = None,
    data_delete_at: Optional[datetime] = None,
) -> PolicyDecision:
    if state in _FULL_ACCESS_COMPANY_STATES:
        return _ALLOWED
    if state is CompanyState.SUSPENDED:
        return _denied(ReasonCode.COMPANY_SUSPENDED)
    if state is CompanyState.CLOSED:
        if now is None or data_delete_at is None:
            return _denied(ReasonCode.COMPANY_SUSPENDED)
        _require_utc(now, "now")
        _require_utc(data_delete_at, "data_delete_at")
        if now >= data_delete_at:
            return _denied(ReasonCode.COMPANY_SUSPENDED)
        if capability in _READ_ONLY_CAPABILITIES:
            return _ALLOWED
        return _denied(ReasonCode.COMPANY_READ_ONLY)
    if state in _READ_ONLY_COMPANY_STATES:
        if capability in _READ_ONLY_CAPABILITIES:
            return _ALLOWED
        return _denied(ReasonCode.COMPANY_READ_ONLY)
    return _denied(ReasonCode.COMPANY_SUSPENDED)


def authorize_tenant_action(
    role: Role,
    operation: TenantOperation,
    company_state: CompanyState,
    membership_status: MembershipStatus,
    assurance_level: AssuranceLevel,
    *,
    now: Optional[datetime] = None,
    company_data_delete_at: Optional[datetime] = None,
) -> PolicyDecision:
    assurance = evaluate_assurance_level(assurance_level)
    if not assurance.allowed:
        return assurance

    membership = evaluate_membership(membership_status)
    if not membership.allowed:
        return membership

    company = evaluate_company_capability(
        company_state,
        _TENANT_OPERATION_CAPABILITIES[operation],
        now=now,
        data_delete_at=company_data_delete_at,
    )
    if not company.allowed:
        return company

    if operation not in _ROLE_PERMISSIONS[role]:
        return _denied(ReasonCode.INSUFFICIENT_ROLE)
    return _ALLOWED


def authorize_platform_action(
    role: Role,
    operation: PlatformOperation,
    assurance_level: AssuranceLevel,
) -> PolicyDecision:
    assurance = evaluate_assurance_level(assurance_level)
    if not assurance.allowed:
        return assurance
    if role is not Role.PLATFORM_ADMIN:
        return _denied(ReasonCode.INSUFFICIENT_ROLE)
    return _ALLOWED


def evaluate_session(
    session: SessionRecord,
    *,
    token_session_id: str,
    token_user_id: str,
    now: datetime,
) -> PolicyDecision:
    _require_utc(now, "now")
    _require_utc(session.absolute_expires_at, "absolute_expires_at")
    if session.revoked_at is not None:
        _require_utc(session.revoked_at, "revoked_at")
        return _denied(ReasonCode.SESSION_REVOKED)
    if (
        token_session_id != session.session_id
        or token_user_id != session.user_id
    ):
        return _denied(ReasonCode.SESSION_INVALID)
    if now >= session.absolute_expires_at:
        return _denied(ReasonCode.SESSION_EXPIRED)
    return _ALLOWED


def normalize_email(email: str) -> str:
    return email.strip().lower()


def evaluate_invitation(
    invitation: InvitationRecord,
    *,
    authenticated_email: str,
    now: datetime,
) -> PolicyDecision:
    _require_utc(now, "now")
    _require_utc(invitation.expires_at, "expires_at")
    if invitation.status is InvitationStatus.EXPIRED:
        return _denied(ReasonCode.INVITATION_EXPIRED)
    if invitation.status is not InvitationStatus.PENDING:
        return _denied(ReasonCode.INVITATION_INVALID)
    if now >= invitation.expires_at:
        return _denied(ReasonCode.INVITATION_EXPIRED)
    if normalize_email(authenticated_email) != normalize_email(
        invitation.email_normalized
    ):
        return _denied(ReasonCode.EMAIL_MISMATCH)
    return _ALLOWED


def authorize_owner_change(
    actor_role: Role,
    *,
    current_owner_count: int,
    resulting_owner_count: int,
) -> PolicyDecision:
    if current_owner_count < 0 or resulting_owner_count < 0:
        raise ValueError("owner counts must be non-negative")
    if actor_role is not Role.PLATFORM_ADMIN:
        return _denied(ReasonCode.OWNER_CHANGE_FORBIDDEN)
    if resulting_owner_count != 1:
        return _denied(ReasonCode.OWNER_CHANGE_FORBIDDEN)
    return _ALLOWED
