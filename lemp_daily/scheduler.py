from __future__ import annotations
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Iterable

from .models import DailySchedule


class BusinessDayCalendar:
    def __init__(self, holidays: Iterable[str] = ()) -> None:
        self.holidays = set(holidays)

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5 and value.isoformat() not in self.holidays

    def next_business_day(self, value: date) -> date:
        current = value
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current


class DailyScheduler:
    def __init__(self, calendar: BusinessDayCalendar) -> None:
        self.calendar = calendar

    def next_run(
        self,
        schedule: DailySchedule,
        now: datetime,
    ) -> datetime:
        tz = ZoneInfo(schedule.timezone)
        local_now = now.astimezone(tz)
        hour, minute = [int(part) for part in schedule.run_time.split(":")]
        candidate = local_now.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= local_now:
            candidate += timedelta(days=1)

        if schedule.business_days_only:
            next_day = self.calendar.next_business_day(candidate.date())
            candidate = candidate.replace(
                year=next_day.year,
                month=next_day.month,
                day=next_day.day,
            )
        return candidate
