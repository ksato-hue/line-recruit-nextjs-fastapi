from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from authz_policy import (
    AssuranceLevel,
    CompanyCapability,
    CompanyState,
    InvitationRecord,
    InvitationStatus,
    MembershipStatus,
    PlatformOperation,
    PolicyDecision,
    ReasonCode,
    Role,
    SessionRecord,
    TenantOperation,
    authorize_owner_change,
    authorize_platform_action,
    authorize_tenant_action,
    evaluate_assurance_level,
    evaluate_company_capability,
    evaluate_invitation,
    evaluate_membership,
    evaluate_session,
    normalize_email,
)


UTC = timezone.utc
NOW = datetime(2026, 7, 24, 12, 0, 0, tzinfo=UTC)


class RolePolicyTests(unittest.TestCase):
    def authorize(self, role: Role, operation: TenantOperation) -> PolicyDecision:
        return authorize_tenant_action(
            role,
            operation,
            CompanyState.ACTIVE,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
        )

    def assert_allowed(self, decision: PolicyDecision) -> None:
        self.assertTrue(decision.allowed)
        self.assertIsNone(decision.reason_code)

    def assert_insufficient_role(self, decision: PolicyDecision) -> None:
        self.assertFalse(decision.allowed)
        self.assertEqual(ReasonCode.INSUFFICIENT_ROLE, decision.reason_code)

    def test_owner_can_perform_every_tenant_operation(self) -> None:
        for operation in TenantOperation:
            with self.subTest(operation=operation):
                self.assert_allowed(self.authorize(Role.OWNER, operation))

    def test_admin_can_read_applicants(self) -> None:
        self.assert_allowed(
            self.authorize(Role.ADMIN, TenantOperation.APPLICANT_READ)
        )

    def test_admin_can_update_applicants(self) -> None:
        self.assert_allowed(
            self.authorize(Role.ADMIN, TenantOperation.APPLICANT_UPDATE)
        )

    def test_admin_can_send_messages(self) -> None:
        self.assert_allowed(self.authorize(Role.ADMIN, TenantOperation.MESSAGE_SEND))

    def test_admin_can_manage_interviews(self) -> None:
        self.assert_allowed(
            self.authorize(Role.ADMIN, TenantOperation.INTERVIEW_MANAGE)
        )

    def test_admin_can_read_settings(self) -> None:
        self.assert_allowed(
            self.authorize(Role.ADMIN, TenantOperation.SETTINGS_READ)
        )

    def test_admin_can_update_settings(self) -> None:
        self.assert_allowed(
            self.authorize(Role.ADMIN, TenantOperation.SETTINGS_UPDATE)
        )

    def test_admin_cannot_read_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.ADMIN, TenantOperation.MEMBER_READ)
        )

    def test_admin_cannot_invite_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.ADMIN, TenantOperation.MEMBER_INVITE)
        )

    def test_admin_cannot_suspend_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.ADMIN, TenantOperation.MEMBER_SUSPEND)
        )

    def test_admin_cannot_update_member_roles(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.ADMIN, TenantOperation.MEMBER_ROLE_UPDATE)
        )

    def test_admin_cannot_export_csv(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.ADMIN, TenantOperation.CSV_EXPORT)
        )

    def test_member_can_read_applicants(self) -> None:
        self.assert_allowed(
            self.authorize(Role.MEMBER, TenantOperation.APPLICANT_READ)
        )

    def test_member_can_update_applicants(self) -> None:
        self.assert_allowed(
            self.authorize(Role.MEMBER, TenantOperation.APPLICANT_UPDATE)
        )

    def test_member_can_send_messages(self) -> None:
        self.assert_allowed(self.authorize(Role.MEMBER, TenantOperation.MESSAGE_SEND))

    def test_member_can_manage_interviews(self) -> None:
        self.assert_allowed(
            self.authorize(Role.MEMBER, TenantOperation.INTERVIEW_MANAGE)
        )

    def test_member_can_read_required_settings(self) -> None:
        self.assert_allowed(
            self.authorize(Role.MEMBER, TenantOperation.SETTINGS_READ)
        )

    def test_member_cannot_update_settings(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.SETTINGS_UPDATE)
        )

    def test_member_cannot_read_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.MEMBER_READ)
        )

    def test_member_cannot_invite_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.MEMBER_INVITE)
        )

    def test_member_cannot_suspend_members(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.MEMBER_SUSPEND)
        )

    def test_member_cannot_update_member_roles(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.MEMBER_ROLE_UPDATE)
        )

    def test_member_cannot_export_csv(self) -> None:
        self.assert_insufficient_role(
            self.authorize(Role.MEMBER, TenantOperation.CSV_EXPORT)
        )

    def test_platform_admin_cannot_perform_tenant_operations(self) -> None:
        for operation in TenantOperation:
            with self.subTest(operation=operation):
                self.assert_insufficient_role(
                    self.authorize(Role.PLATFORM_ADMIN, operation)
                )

    def test_platform_admin_can_perform_platform_operations(self) -> None:
        for operation in PlatformOperation:
            with self.subTest(operation=operation):
                self.assert_allowed(
                    authorize_platform_action(
                        Role.PLATFORM_ADMIN,
                        operation,
                        AssuranceLevel.AAL2,
                    )
                )

    def test_tenant_owner_cannot_perform_platform_operations(self) -> None:
        self.assert_insufficient_role(
            authorize_platform_action(
                Role.OWNER,
                PlatformOperation.COMPANY_METADATA_READ,
                AssuranceLevel.AAL2,
            )
        )

    def test_platform_operations_require_aal2(self) -> None:
        decision = authorize_platform_action(
            Role.PLATFORM_ADMIN,
            PlatformOperation.COMPANY_METADATA_READ,
            AssuranceLevel.AAL1,
        )
        self.assertEqual(
            PolicyDecision(False, ReasonCode.MFA_REQUIRED),
            decision,
        )


class CompanyPolicyTests(unittest.TestCase):
    def assert_allowed(self, decision: PolicyDecision) -> None:
        self.assertEqual(PolicyDecision(True, None), decision)

    def test_monitor_active_allows_every_capability(self) -> None:
        for capability in CompanyCapability:
            with self.subTest(capability=capability):
                self.assert_allowed(
                    evaluate_company_capability(
                        CompanyState.MONITOR_ACTIVE,
                        capability,
                    )
                )

    def test_active_allows_every_capability(self) -> None:
        for capability in CompanyCapability:
            with self.subTest(capability=capability):
                self.assert_allowed(
                    evaluate_company_capability(CompanyState.ACTIVE, capability)
                )

    def test_monitor_expired_allows_dashboard_read(self) -> None:
        self.assert_allowed(
            evaluate_company_capability(
                CompanyState.MONITOR_EXPIRED,
                CompanyCapability.DASHBOARD_READ,
            )
        )

    def test_monitor_expired_allows_csv_export(self) -> None:
        self.assert_allowed(
            evaluate_company_capability(
                CompanyState.MONITOR_EXPIRED,
                CompanyCapability.CSV_EXPORT,
            )
        )

    def test_monitor_expired_rejects_dashboard_write(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_READ_ONLY),
            evaluate_company_capability(
                CompanyState.MONITOR_EXPIRED,
                CompanyCapability.DASHBOARD_WRITE,
            ),
        )

    def test_monitor_expired_rejects_line_acceptance(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_READ_ONLY),
            evaluate_company_capability(
                CompanyState.MONITOR_EXPIRED,
                CompanyCapability.LINE_ACCEPT,
            ),
        )

    def test_suspended_rejects_every_capability(self) -> None:
        for capability in CompanyCapability:
            with self.subTest(capability=capability):
                self.assertEqual(
                    PolicyDecision(False, ReasonCode.COMPANY_SUSPENDED),
                    evaluate_company_capability(
                        CompanyState.SUSPENDED,
                        capability,
                    ),
                )

    def test_closed_allows_dashboard_read_during_retention(self) -> None:
        self.assert_allowed(
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.DASHBOARD_READ,
                now=NOW,
                data_delete_at=NOW + timedelta(seconds=1),
            )
        )

    def test_closed_allows_csv_export_during_retention(self) -> None:
        self.assert_allowed(
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.CSV_EXPORT,
                now=NOW,
                data_delete_at=NOW + timedelta(seconds=1),
            )
        )

    def test_closed_rejects_dashboard_write(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_READ_ONLY),
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.DASHBOARD_WRITE,
                now=NOW,
                data_delete_at=NOW + timedelta(days=1),
            ),
        )

    def test_closed_rejects_line_acceptance(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_READ_ONLY),
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.LINE_ACCEPT,
                now=NOW,
                data_delete_at=NOW + timedelta(days=1),
            ),
        )

    def test_closed_rejects_read_exactly_at_deletion_time(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_SUSPENDED),
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.DASHBOARD_READ,
                now=NOW,
                data_delete_at=NOW,
            ),
        )

    def test_closed_rejects_csv_after_deletion_time(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_SUSPENDED),
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.CSV_EXPORT,
                now=NOW,
                data_delete_at=NOW - timedelta(seconds=1),
            ),
        )

    def test_closed_without_retention_dates_fails_closed(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_SUSPENDED),
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.DASHBOARD_READ,
            ),
        )

    def test_closed_rejects_naive_retention_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "data_delete_at must be UTC"):
            evaluate_company_capability(
                CompanyState.CLOSED,
                CompanyCapability.DASHBOARD_READ,
                now=NOW,
                data_delete_at=(NOW + timedelta(days=1)).replace(tzinfo=None),
            )


class MembershipPolicyTests(unittest.TestCase):
    def test_active_membership_is_allowed(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            evaluate_membership(MembershipStatus.ACTIVE),
        )

    def test_pending_membership_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.MEMBERSHIP_NOT_ACTIVE),
            evaluate_membership(MembershipStatus.PENDING),
        )

    def test_suspended_membership_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.MEMBERSHIP_NOT_ACTIVE),
            evaluate_membership(MembershipStatus.SUSPENDED),
        )


class MfaPolicyTests(unittest.TestCase):
    def test_aal2_is_allowed(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            evaluate_assurance_level(AssuranceLevel.AAL2),
        )

    def test_aal1_returns_structured_mfa_required(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.MFA_REQUIRED),
            evaluate_assurance_level(AssuranceLevel.AAL1),
        )


class CompositeTenantPolicyTests(unittest.TestCase):
    def test_mfa_failure_has_first_precedence(self) -> None:
        decision = authorize_tenant_action(
            Role.MEMBER,
            TenantOperation.CSV_EXPORT,
            CompanyState.SUSPENDED,
            MembershipStatus.SUSPENDED,
            AssuranceLevel.AAL1,
        )
        self.assertEqual(ReasonCode.MFA_REQUIRED, decision.reason_code)

    def test_membership_failure_precedes_company_and_role(self) -> None:
        decision = authorize_tenant_action(
            Role.MEMBER,
            TenantOperation.CSV_EXPORT,
            CompanyState.SUSPENDED,
            MembershipStatus.PENDING,
            AssuranceLevel.AAL2,
        )
        self.assertEqual(ReasonCode.MEMBERSHIP_NOT_ACTIVE, decision.reason_code)

    def test_read_only_company_allows_csv_then_role_denies(self) -> None:
        decision = authorize_tenant_action(
            Role.MEMBER,
            TenantOperation.CSV_EXPORT,
            CompanyState.MONITOR_EXPIRED,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
        )
        self.assertEqual(ReasonCode.INSUFFICIENT_ROLE, decision.reason_code)

    def test_read_only_company_blocks_write_for_owner(self) -> None:
        decision = authorize_tenant_action(
            Role.OWNER,
            TenantOperation.APPLICANT_UPDATE,
            CompanyState.MONITOR_EXPIRED,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
        )
        self.assertEqual(ReasonCode.COMPANY_READ_ONLY, decision.reason_code)

    def test_suspended_company_blocks_read_before_role_check(self) -> None:
        decision = authorize_tenant_action(
            Role.PLATFORM_ADMIN,
            TenantOperation.APPLICANT_READ,
            CompanyState.SUSPENDED,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
        )
        self.assertEqual(ReasonCode.COMPANY_SUSPENDED, decision.reason_code)

    def test_closed_company_allows_read_before_deletion_time(self) -> None:
        decision = authorize_tenant_action(
            Role.OWNER,
            TenantOperation.APPLICANT_READ,
            CompanyState.CLOSED,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
            now=NOW,
            company_data_delete_at=NOW + timedelta(seconds=1),
        )
        self.assertEqual(PolicyDecision(True, None), decision)

    def test_closed_company_blocks_read_at_deletion_time(self) -> None:
        decision = authorize_tenant_action(
            Role.OWNER,
            TenantOperation.APPLICANT_READ,
            CompanyState.CLOSED,
            MembershipStatus.ACTIVE,
            AssuranceLevel.AAL2,
            now=NOW,
            company_data_delete_at=NOW,
        )
        self.assertEqual(
            PolicyDecision(False, ReasonCode.COMPANY_SUSPENDED),
            decision,
        )


class SessionPolicyTests(unittest.TestCase):
    def session(
        self,
        *,
        expires_at: datetime = NOW + timedelta(days=30),
        revoked_at: datetime | None = None,
    ) -> SessionRecord:
        return SessionRecord(
            session_id="session-a",
            user_id="user-a",
            absolute_expires_at=expires_at,
            revoked_at=revoked_at,
        )

    def evaluate(
        self,
        session: SessionRecord,
        *,
        token_session_id: str = "session-a",
        token_user_id: str = "user-a",
        now: datetime = NOW,
    ) -> PolicyDecision:
        return evaluate_session(
            session,
            token_session_id=token_session_id,
            token_user_id=token_user_id,
            now=now,
        )

    def test_valid_session_is_allowed(self) -> None:
        self.assertEqual(PolicyDecision(True, None), self.evaluate(self.session()))

    def test_session_is_valid_one_second_before_expiry(self) -> None:
        expires_at = NOW + timedelta(seconds=1)
        self.assertEqual(
            PolicyDecision(True, None),
            self.evaluate(self.session(expires_at=expires_at), now=NOW),
        )

    def test_session_expires_exactly_at_absolute_expiry(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.SESSION_EXPIRED),
            self.evaluate(self.session(expires_at=NOW), now=NOW),
        )

    def test_session_is_expired_one_second_after_expiry(self) -> None:
        expires_at = NOW - timedelta(seconds=1)
        self.assertEqual(
            PolicyDecision(False, ReasonCode.SESSION_EXPIRED),
            self.evaluate(self.session(expires_at=expires_at), now=NOW),
        )

    def test_revoked_session_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.SESSION_REVOKED),
            self.evaluate(self.session(revoked_at=NOW - timedelta(seconds=1))),
        )

    def test_session_id_mismatch_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.SESSION_INVALID),
            self.evaluate(self.session(), token_session_id="session-b"),
        )

    def test_user_id_mismatch_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.SESSION_INVALID),
            self.evaluate(self.session(), token_user_id="user-b"),
        )

    def test_naive_session_now_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "now must be UTC"):
            self.evaluate(self.session(), now=NOW.replace(tzinfo=None))

    def test_non_utc_session_now_is_rejected(self) -> None:
        japan = timezone(timedelta(hours=9))
        with self.assertRaisesRegex(ValueError, "now must be UTC"):
            self.evaluate(self.session(), now=NOW.astimezone(japan))

    def test_naive_session_expiry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute_expires_at must be UTC"):
            self.evaluate(
                self.session(expires_at=(NOW + timedelta(days=1)).replace(tzinfo=None))
            )

    def test_naive_revoked_at_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "revoked_at must be UTC"):
            self.evaluate(
                self.session(
                    revoked_at=(NOW - timedelta(seconds=1)).replace(tzinfo=None)
                )
            )


class InvitationPolicyTests(unittest.TestCase):
    def invitation(
        self,
        *,
        status: InvitationStatus = InvitationStatus.PENDING,
        email: str = "user@example.test",
        expires_at: datetime = NOW + timedelta(days=7),
    ) -> InvitationRecord:
        return InvitationRecord(
            status=status,
            email_normalized=email,
            expires_at=expires_at,
        )

    def test_email_normalization_strips_and_lowercases(self) -> None:
        self.assertEqual(
            "user@example.test",
            normalize_email("  USER@EXAMPLE.TEST  "),
        )

    def test_pending_invitation_within_expiry_is_allowed(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            evaluate_invitation(
                self.invitation(),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_invitation_expires_exactly_at_expiry(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.INVITATION_EXPIRED),
            evaluate_invitation(
                self.invitation(expires_at=NOW),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_invitation_is_expired_one_second_after_expiry(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.INVITATION_EXPIRED),
            evaluate_invitation(
                self.invitation(expires_at=NOW - timedelta(seconds=1)),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_accepted_invitation_is_invalid(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.INVITATION_INVALID),
            evaluate_invitation(
                self.invitation(status=InvitationStatus.ACCEPTED),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_revoked_invitation_is_invalid(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.INVITATION_INVALID),
            evaluate_invitation(
                self.invitation(status=InvitationStatus.REVOKED),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_expired_status_returns_invitation_expired(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.INVITATION_EXPIRED),
            evaluate_invitation(
                self.invitation(status=InvitationStatus.EXPIRED),
                authenticated_email="user@example.test",
                now=NOW,
            ),
        )

    def test_email_mismatch_is_rejected(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.EMAIL_MISMATCH),
            evaluate_invitation(
                self.invitation(),
                authenticated_email="other@example.test",
                now=NOW,
            ),
        )

    def test_normalized_email_exact_match_is_allowed(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            evaluate_invitation(
                self.invitation(email="user@example.test"),
                authenticated_email="  USER@EXAMPLE.TEST  ",
                now=NOW,
            ),
        )

    def test_naive_invitation_now_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "now must be UTC"):
            evaluate_invitation(
                self.invitation(),
                authenticated_email="user@example.test",
                now=NOW.replace(tzinfo=None),
            )

    def test_naive_invitation_expiry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "expires_at must be UTC"):
            evaluate_invitation(
                self.invitation(
                    expires_at=(NOW + timedelta(days=7)).replace(tzinfo=None)
                ),
                authenticated_email="user@example.test",
                now=NOW,
            )


class OwnerConstraintTests(unittest.TestCase):
    def test_platform_admin_can_transfer_single_owner(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            authorize_owner_change(
                Role.PLATFORM_ADMIN,
                current_owner_count=1,
                resulting_owner_count=1,
            ),
        )

    def test_platform_admin_can_create_first_owner(self) -> None:
        self.assertEqual(
            PolicyDecision(True, None),
            authorize_owner_change(
                Role.PLATFORM_ADMIN,
                current_owner_count=0,
                resulting_owner_count=1,
            ),
        )

    def test_owner_cannot_transfer_owner_from_tenant_context(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.OWNER_CHANGE_FORBIDDEN),
            authorize_owner_change(
                Role.OWNER,
                current_owner_count=1,
                resulting_owner_count=1,
            ),
        )

    def test_admin_cannot_change_owner(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.OWNER_CHANGE_FORBIDDEN),
            authorize_owner_change(
                Role.ADMIN,
                current_owner_count=1,
                resulting_owner_count=1,
            ),
        )

    def test_member_cannot_change_owner(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.OWNER_CHANGE_FORBIDDEN),
            authorize_owner_change(
                Role.MEMBER,
                current_owner_count=1,
                resulting_owner_count=1,
            ),
        )

    def test_owner_change_cannot_leave_zero_owners(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.OWNER_CHANGE_FORBIDDEN),
            authorize_owner_change(
                Role.PLATFORM_ADMIN,
                current_owner_count=1,
                resulting_owner_count=0,
            ),
        )

    def test_owner_change_cannot_create_multiple_owners(self) -> None:
        self.assertEqual(
            PolicyDecision(False, ReasonCode.OWNER_CHANGE_FORBIDDEN),
            authorize_owner_change(
                Role.PLATFORM_ADMIN,
                current_owner_count=1,
                resulting_owner_count=2,
            ),
        )

    def test_negative_owner_counts_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "owner counts"):
            authorize_owner_change(
                Role.PLATFORM_ADMIN,
                current_owner_count=-1,
                resulting_owner_count=1,
            )


if __name__ == "__main__":
    unittest.main()
