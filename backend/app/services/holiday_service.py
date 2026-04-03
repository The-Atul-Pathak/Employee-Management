from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import Holiday, HolidayType
from app.schemas.holiday import HolidayCreate, HolidayResponse

# Indian national and major holidays by month-day (MM, DD) and name.
# These are seeded when a company is created.
_INDIAN_NATIONAL_HOLIDAYS_2025: list[tuple[int, int, str]] = [
    (1, 26, "Republic Day"),
    (3, 14, "Holi"),
    (4, 14, "Ambedkar Jayanti"),
    (4, 18, "Good Friday"),
    (5, 1, "Labour Day / Maharashtra Day"),
    (8, 15, "Independence Day"),
    (10, 2, "Gandhi Jayanti"),
    (10, 20, "Diwali"),
    (10, 21, "Diwali (Second Day)"),
    (12, 25, "Christmas Day"),
]


class HolidayService:
    async def list_holidays(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        year: int | None = None,
    ) -> list[HolidayResponse]:
        stmt = select(Holiday).where(Holiday.company_id == company_id)
        if year is not None:
            stmt = stmt.where(Holiday.year == year)
        stmt = stmt.order_by(Holiday.date.asc())
        rows = (await db.execute(stmt)).scalars().all()
        return [HolidayResponse.model_validate(h) for h in rows]

    async def create_holiday(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        data: HolidayCreate,
    ) -> HolidayResponse:
        existing = (
            await db.execute(
                select(Holiday).where(
                    Holiday.company_id == company_id,
                    Holiday.date == data.date,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"A holiday already exists on {data.date}")

        holiday = Holiday(
            company_id=company_id,
            name=data.name,
            date=data.date,
            holiday_type=data.holiday_type,
            is_optional=data.is_optional,
            year=data.date.year,
        )
        db.add(holiday)
        await db.flush()
        await db.refresh(holiday)
        return HolidayResponse.model_validate(holiday)

    async def delete_holiday(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        holiday_id: uuid.UUID,
    ) -> None:
        holiday = (
            await db.execute(
                select(Holiday).where(
                    Holiday.id == holiday_id,
                    Holiday.company_id == company_id,
                )
            )
        ).scalar_one_or_none()
        if holiday is None:
            raise LookupError("Holiday not found")
        await db.delete(holiday)
        await db.flush()

    async def bulk_load_standard_holidays(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        year: int,
    ) -> list[HolidayResponse]:
        """Seed Indian national holidays for the given year. Skips duplicates."""
        created: list[HolidayResponse] = []
        for month, day, name in _INDIAN_NATIONAL_HOLIDAYS_2025:
            try:
                holiday_date = date(year, month, day)
            except ValueError:
                continue

            existing = (
                await db.execute(
                    select(Holiday).where(
                        Holiday.company_id == company_id,
                        Holiday.date == holiday_date,
                    )
                )
            ).scalar_one_or_none()

            if existing is not None:
                continue

            holiday = Holiday(
                company_id=company_id,
                name=name,
                date=holiday_date,
                holiday_type=HolidayType.national,
                is_optional=False,
                year=year,
            )
            db.add(holiday)
            await db.flush()
            await db.refresh(holiday)
            created.append(HolidayResponse.model_validate(holiday))

        return created

    async def get_holiday_dates(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        year: int,
    ) -> set[date]:
        """Return a set of holiday dates for quick calendar lookups."""
        stmt = select(Holiday.date).where(
            Holiday.company_id == company_id,
            Holiday.year == year,
            Holiday.is_optional.is_(False),
        )
        rows = (await db.execute(stmt)).scalars().all()
        return set(rows)


holiday_service = HolidayService()


async def seed_company_holidays(company_id: uuid.UUID, db: AsyncSession) -> None:
    """Seed standard Indian national holidays for the current year.

    Called from platform_service when a company is created.
    Idempotent — skips dates that already exist.
    """
    current_year = date.today().year
    await holiday_service.bulk_load_standard_holidays(db, company_id, current_year)
