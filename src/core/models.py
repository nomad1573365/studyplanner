from datetime import date, datetime, timedelta
import math
from dataclasses import dataclass

from src.core.exception import DomainError

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
            raise DomainError("終了地点が開始地点より手前にあります。")

        if current_point < 0:
            raise DomainError()

        if current_point > self._total_amount:
            raise DomainError("ゴール地点を超過しています。")
        
        if end_date < start_date:
            raise DomainError("終了日が開始日より手前にあります。")

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
    
    @property
    def goal_id(self):
        return self._goal_id

    def remaining(self) -> int:
        return int(self._total_amount - self._current_point)

    def remaining_days(self, ref_date) -> int:
        delta = (self._end_date - ref_date).days + 1
        return max(delta, 0)

    def required_pages_per_day(self) -> float:
        days = self.remaining_days(date.today())
        if days == 0:
            return float("inf")
        return self.remaining() / days

    def is_completed(self) -> bool:
        return self._current_point >= self._total_amount

    def is_overdue(self) -> bool:
        return date.today() > self._end_date and not self.is_completed()
    
    def is_out_of_period(self, ref_date) -> bool:
        if self._start_date > ref_date:
            return True
        return False

    def add_progress(self, amount: int):
        if amount <= 0:
            raise DomainError("amountは正の値にしてください。")
        if self._current_point + amount > self._total_amount:
            raise DomainError("記録がゴール地点を超過してしまいます。")
        self._current_point += amount

    def daily_amount(self, ref_date):
        days_left = self.remaining_days(ref_date)
        if days_left > 0:
            return math.ceil(self.remaining() / days_left) 
        else:
            return self.remaining() if self.remaining() > 0 else 0
        
    def get_weekly_goal(self, ref_date: date, weight: float = 1.0):
        remaining = int(self.remaining())
        if remaining <= 0:
            return 0
        days_left = self.remaining_days(ref_date)
        
        this_monday = ref_date - timedelta(days=ref_date.weekday())
        this_sunday = ref_date + timedelta(days=(6 - ref_date.weekday()))
        active_start = max(this_monday, self._start_date)
        active_end = min(this_sunday, self._end_date)
        active_days_in_week = (active_end - active_start).days + 1
        
        if days_left <= 0:
            return remaining

        if active_days_in_week <= 0:
            return 0
        
        required_daily_pace = remaining / days_left
        weekly_goal = required_daily_pace * active_days_in_week * weight
        return math.ceil(weekly_goal)

    def calculate_daily_amount(self, weekly_actual_sum: int, ref_date: date, weight: float = 1.0):
        weekly_amount = self.get_weekly_goal(ref_date, weight)
        weekly_remaining_amount = max(0, weekly_amount - weekly_actual_sum)

        if weekly_remaining_amount <= 0:
            # 週次目標を満たしていても、未完了ゴールの plan_amount は 1 以上を維持する
            # (DB 制約および UI 側の 0 除算回避)
            return 1 if self.remaining() > 0 else 0

        weekday = ref_date.weekday()
        days_left = 6 - weekday

        
        if weekday == 6: # 日曜日の処理
            daily_amount = weekly_remaining_amount
        else: # 他の日の処理
            active_days_in_week = min(7, (self._end_date - self._start_date).days + 1)
            work_days = max(1, active_days_in_week - 1) 
            base_daily = weekly_amount / work_days

            balanced_daily = weekly_remaining_amount / days_left

            daily_amount = max(base_daily, balanced_daily, 1)
            daily_amount = min(daily_amount, self.remaining())

        if not self.remaining_days(ref_date):
            daily_amount = self.remaining()

        return math.ceil(min(daily_amount, self.remaining()))
        


class DailyTask:
    def __init__(
        self,
        goal_id: int,
        user_id: str,
        goal_name: str,
        plan_amount: int,
        actual_amount: int,
        is_completed: bool,
        current_point: int, 
        goal_start_point: int, 
        ):
        if any(x is None for x in [goal_id, user_id, goal_name, plan_amount, actual_amount, is_completed, current_point, goal_start_point]):
            raise DomainError("必要情報が不足しています。")
        self._goal_id = goal_id
        self._user_id = user_id
        self._goal_name = goal_name
        self._plan_amount = plan_amount
        self._actual_amount = actual_amount
        self._is_completed = is_completed
        self._current_point = current_point
        self._goal_start_point = goal_start_point
        
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
    def plan_amount(self):
        return self._plan_amount
    
    @property
    def actual_amount(self):
        return self._actual_amount
    
    @property
    def is_completed(self):
        return self._is_completed
    
    @property
    def current_point(self):
        return self._current_point
    
    @property
    def today_start_point(self):
        return self._goal_start_point + self._current_point

class Objective:
    def __init__(self, user_id: int, objective: str):
        if user_id is None or objective is None:
            raise DomainError("必要な情報が不足しています。")
        self._user_id = user_id
        self._objective = objective
    
    @property
    def user_id(self):
        return self._user_id
    
    @property
    def objective(self):
        return self._objective
    
    
