from __future__ import annotations
import uuid
import enum
from decimal import Decimal
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as PgEnum

from app.models.base import Base, BaseModel


class BillingCycle(str, enum.Enum):
    monthly = "monthly"
    yearly = "yearly"


class Plan(BaseModel):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    yearly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_employees: Mapped[int] = mapped_column(Integer, nullable=False)

    subscriptions: Mapped[list["CompanySubscription"]] = relationship(
        "CompanySubscription", back_populates="plan", lazy="select"
    )
    plan_features: Mapped[list["PlanFeature"]] = relationship(
        "PlanFeature", back_populates="plan", lazy="select", cascade="all, delete-orphan"
    )


class PlanFeature(Base):
    __tablename__ = "plan_features"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_id", name="uq_plan_features_plan_feature"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("features.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plan: Mapped["Plan"] = relationship("Plan", back_populates="plan_features")


class CompanySubscription(Base):
    __tablename__ = "company_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        PgEnum(BillingCycle, name="billing_cycle", create_type=True),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions")
