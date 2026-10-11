"""Pydantic-схемы запросов и ответов API."""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    TokenResponse,
    UserInfo,
)
from app.schemas.common import (
    Bucket,
    Counterparty,
    DebtorKind,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    PeriodKind,
)
from app.schemas.dashboard import (
    DebtorItem,
    DebtorsResponse,
    DynamicsItem,
    DynamicsResponse,
    KpiMeta,
    OrganizationItem,
    OrganizationsResponse,
    SummaryResponse,
)

__all__ = [
    "Bucket",
    "Counterparty",
    "DebtorItem",
    "DebtorKind",
    "DebtorsResponse",
    "DynamicsItem",
    "DynamicsResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "KpiMeta",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "MessageResponse",
    "OrganizationItem",
    "OrganizationsResponse",
    "PeriodKind",
    "RefreshResponse",
    "SummaryResponse",
    "TokenResponse",
    "UserInfo",
]
