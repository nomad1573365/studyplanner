from datetime import date, datetime, timedelta
import math
from dataclasses import dataclass



class DomainError(Exception):
    pass

"""
class Objective: #目標
    def __init__(self, objective):
        self.objective = objective
"""

class User:
    def __init__(self, user_id: int, name: str):
        self._id = user_id
        self._name = name

    @property
    def id(self):
        return self._id
    
    @property
    def name(self):
        return self._name



class Goal:
    def __init__(
        self,
        user_id: int,
        goal_name: str,
        start_point: int,
        end_point: int,
        start_date: date,
        end_date: date,
        current_point: int = 0,
        goal_id: int = None
        ):
        self._user_id = user_id
        self._goal_name = goal_name
        self._start_point = start_point
        self._end_point = end_point
        self._total_amount = end_point - start_point + 1
        self._current_point = current_point
        self._start_date = start_date
        self._end_date = end_date
        self._goal_id = goal_id

        if end_point < start_point:
            raise DomainError()

        if current_point < 0:
            raise DomainError()

        if current_point > self._total_amount:
            raise DomainError()
        
        if end_date < start_date:
            raise DomainError()

    @property
    def goal_id(self):
        return self._goal_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def goal_name(self):
        return self._goal_name

    @property
    def start_point(self):
        return self._start_point

    @property
    def end_point(self):
        return self._end_point

    @property
    def total_amount(self):
        return self._total_amount

    @property
    def current_point(self):
        return self._current_point

    @property
    def start_date(self):
        return self._start_date

    @property
    def end_date(self):
        return self._end_date

    def remaining(self) -> int:
        return self._total_amount - self._current_point

    def remaining_days(self, ref_date=date.today()) -> int:
        delta = (self._end_date - ref_date).days
        return max(delta, 0)

    def required_pages_per_day(self) -> float:
        days = self.remaining_days()
        if days == 0:
            return float("inf")
        return self.remaining() / days

    def is_completed(self, ref_date=date.today()) -> bool:
        return self._current_point >= self._total_amount

    def is_overdue(self) -> bool:
        return date.today() > self._end_date and not self.is_completed()
    
    def is_out_of_period(self, ref_date=date.today()) -> bool:
        if self._start_date > ref_date:
            return True
        return False

    def add_progress(self, amount: int):
        if amount <= 0:
            raise DomainError()
        if self._current_point + amount > self._total_amount:
            raise DomainError()
        self._current_point += amount

    def daily_amount(self):
        days_left = self.remaining_days()
        if days_left > 0:
            return math.ceil(self.remaining() / days_left) 
        else:
            return self.remaining() if self.remaining() > 0 else 0
        
    def get_weekly_amount(self, weight=1.0):
        remaining = self.remaining()
        if remaining <= 0:
            return 0

        days_left = self.remaining_days()
        if days_left <= 0:
            return remaining

        weekly_goal = float(remaining) * float(weight) * min(7, days_left) / days_left

        return math.ceil(weekly_goal)

    def calculate_daily_amount(self, weekly_actual_sum: int, weight: float = 1.0):
        remaining = self.remaining()
        if remaining <= 0:
            return 0

        remaining_days = self.remaining_days()
        if remaining_days <= 0:
            return remaining

        today = date.today()
        weekday = today.weekday()

        week_start = today - timedelta(days=weekday)
        week_end = week_start + timedelta(days=6)

        days_left = max(1, (week_end - today).days + 1)

        base_daily = float(remaining) / remaining_days

        active_start = max(self._start_date, week_start)
        active_end = min(self._end_date, week_end)

        if active_start > active_end:
            return 0

        week_active_days = (active_end - active_start).days + 1

        weekly_target = math.ceil(base_daily * week_active_days * weight)
        weekly_target = min(weekly_target, remaining)

        remaining_week = max(0, weekly_target - weekly_actual_sum)

        daily = math.ceil(remaining_week / days_left)

        return min(daily, remaining)


class ProgressLog:
    def __init__(
        self,
        log_id: int,
        goal_id: int,
        amount: int,
        logged_at: date | None = None,
    ):
        if amount <= 0:
            raise DomainError()

        self._id = log_id
        self._goal_id = goal_id
        self._pages = amount
        self._logged_at = logged_at or date.today()

    @property
    def goal_id(self):
        return self._goal_id

    @property
    def pages(self):
        return self._pages

    @property
    def logged_at(self):
        return self._logged_at
    