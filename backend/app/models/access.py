from __future__ import annotations
from typing import Optional
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BaseModel


class Role(BaseModel):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_roles_company_name"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="role", lazy="select"
    )
    role_features: Mapped[list["RolesFeature"]] = relationship(
        "RolesFeature", back_populates="role", lazy="select"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="user_roles")
    role: Mapped["Role"] = relationship("Role", back_populates="user_roles")


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    role_features: Mapped[list["RolesFeature"]] = relationship(
        "RolesFeature", back_populates="feature", lazy="select"
    )
    pages: Mapped[list["FeaturePage"]] = relationship(
        "FeaturePage", back_populates="feature", lazy="select"
    )


class FeaturePage(Base):
    __tablename__ = "feature_pages"
    __table_args__ = (
        UniqueConstraint("feature_id", "page_code", name="uq_feature_pages_feature_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_code: Mapped[str] = mapped_column(String(100), nullable=False)
    page_name: Mapped[str] = mapped_column(String(150), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    feature: Mapped["Feature"] = relationship("Feature", back_populates="pages")


class RolesFeature(Base):
    __tablename__ = "roles_features"
    __table_args__ = (
        UniqueConstraint("role_id", "feature_id", name="uq_roles_features_role_feature"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped["Role"] = relationship("Role", back_populates="role_features")
    feature: Mapped["Feature"] = relationship("Feature", back_populates="role_features")
