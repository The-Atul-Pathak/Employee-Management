from __future__ import annotations
from typing import Optional
import uuid
import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as PgEnum

from app.models.base import Base


class PlatformAdminRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    SUPPORT = "SUPPORT"


class PlatformAdminStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[PlatformAdminRole] = mapped_column(
        PgEnum(PlatformAdminRole, name="platform_admin_role", create_type=True),
        nullable=False,
    )
    status: Mapped[PlatformAdminStatus] = mapped_column(
        PgEnum(PlatformAdminStatus, name="platform_admin_status", create_type=True),
        nullable=False,
        default=PlatformAdminStatus.active,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sessions: Mapped[list["PlatformSession"]] = relationship(
        "PlatformSession", back_populates="admin", lazy="select"
    )


class PlatformSession(Base):
    __tablename__ = "platform_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    admin: Mapped["PlatformAdmin"] = relationship(
        "PlatformAdmin", back_populates="sessions"
    )
