from src.core import models as md, database as db
from abc import ABC, abstractmethod
from src.core.models import Goal, User, DailyTask
from src.core.exception import NotFoundError, DomainError

from datetime import date, datetime, timedelta
import pandas
import math

today = date.today()

class UserRepository:
    async def get_by_id(self, user_id: int):
        row = await db.fetch_user_record(user_id)
        if row is None:
            raise ValueError("User not found")
        _, username, created_at = row
        return md.User(user_id, username, created_at)

    async def ensure_user(self, username): # -> user_id
        await db.add_user(username)
        return await db.fetch_user_id(username)

async def record_actual_progress(goal_id, actual_amount, ref_date):
    if not goal_id:
        raise NotFoundError
    if actual_amount is None or actual_amount <= 0:
        raise DomainError("値が不正です（amountは1以上にしてください）。")

    goal = await PgGoalRepository().find_by_id(goal_id)
    if actual_amount > goal.remaining():
        raise DomainError(f"値が不正です（残りは {goal.remaining()} です）。")

    return await db.add_actual_progress(goal_id, actual_amount, ref_date)
    
async def add_daily_plan(user_id, goal_name, plan_amount):
    goal_id = await db.fetch_goal_id(user_id, goal_name)
    if not goal_id:
        raise NotFoundError
    await db.add_plan(goal_id, plan_amount, date.today())


async def add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
    goal = md.Goal(user_id, goal_name, start_point, end_point, start_date, end_date)
    if not goal:
        raise NotFoundError
    await db.add_goal(user_id, goal_name, start_point, end_point, start_date, end_date)


async def get_user_goal_models(user_id):
    rows = await db.fetch_goal_with_progress(user_id)
    output = []
    for row in rows:
        goal = md.Goal(
            user_id=user_id,
            goal_id=row['id'],
            goal_name=row['goal_name'],
            start_point=row['start_point'],
            end_point=row['end_point'],
            start_date=row['start_date'],
            end_date=row['end_date'],
            current_point=row['current_point'],
        )
        output.append(goal)
    return output


async def get_user_goal_list(user_id, ref_date): # [["id", "ゴール名", "開始地点", "終了地点", "開始日", "終了日", "現在地点"], ...]
    goal_list = []
    goal_models = await get_user_goal_models(user_id)
    for g in goal_models:
        goal_id, goal_name, start_point, end_point, start_date, end_date, current_point = g.goal_id, g.goal_name, g.start_point, g.end_point, g.start_date, g.end_date, g.current_point
        if g.is_out_of_period(ref_date):
            continue
        goal_list.append([goal_id, goal_name, start_point, end_point, start_date, end_date, current_point])
    return goal_list

async def delete_user(user_id):
    user = PgUserRepository().find_by_id(user_id)
    if not user:
        raise NotFoundError
    return await db.delete_user(user_id)

async def delete_goal(user_id, goal_name):
    goal_id = await db.fetch_goal_id(user_id, goal_name) 
    if not goal_id:
        raise NotFoundError
    return await db.delete_goal(goal_id)

async def delete_user_weight(user_id):
    goal_list = await db.fetch_goal_with_progress(user_id)
    deleted_count = 0
    for goal in goal_list:
        goal_id = goal[0]
        await db.delete_weights(goal_id, date.today())
        deleted_count += 1
    return deleted_count

async def delete_last_record(user_id):
    return await db.delete_last_record(user_id)

from src.core.database import fetch_all, fetch_val, fetch_one, execute_query

class PgGoalRepository:    
    async def find_by_id(self, goal_id) -> Goal:
        row = await fetch_one(
            "SELECT * FROM goals WHERE id = $1",
            goal_id
        )
        if row is None:
            raise NotFoundError

        current = await fetch_val(
            "SELECT SUM(actual_amount) FROM progress_log WHERE goal_id = $1",
            goal_id
        )
        
        return self._to_goal(row, current)
    
    async def find_by_user(self, user_id: int) -> list[Goal]:
        rows = await fetch_all(
            "SELECT * FROM goals WHERE user_id = $1",
            user_id
        )

        goals = []
        for row in rows:
            current = await fetch_val(
                "SELECT SUM(actual_amount) FROM progress_log WHERE goal_id = $1",
                row["id"]
            )
            goals.append(self._to_goal(row, current))

        return goals
    
    async def find_by_name(self, user_id: int, goal_name: str) -> Goal:
        row = await fetch_one(
            "SELECT * FROM goals WHERE user_id = $1 AND goal_name = $2",
            user_id, goal_name
        )
        if row is None:
            return None

        current = await fetch_val(
            "SELECT SUM(actual_amount) FROM progress_log WHERE goal_id = $1",
            row["id"]
        )

        return self._to_goal(row, current)
    
    async def save(self, goal: Goal) -> None:
        await execute_query(
            """
            INSERT INTO goals (id, user_id, goal_name, start_point, end_point, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id)
            DO UPDATE SET
                goal_name = EXCLUDED.goal_name,
                start_point = EXCLUDED.start_point,
                end_point = EXCLUDED.end_point,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date
            """,
            goal.goal_id,
            goal.user_id,
            goal.goal_name,
            goal.start_point,
            goal.end_point,
            goal.start_date,
            goal.end_date
        )
        
    async def delete(self, goal_id: int) -> None:
        await execute_query(
            "DELETE FROM goals WHERE id = $1",
            goal_id
        )
    
    def _to_goal(self, row, current):
        return Goal(
            goal_id=row["id"],
            user_id=row["user_id"],
            goal_name=row["goal_name"],
            start_point=row["start_point"],
            end_point=row["end_point"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            current_point=current or 0
        )

class PgUserRepository:
    async def find_by_id(self, user_id) -> User:
        row = await fetch_one(
            "SELECT id, username FROM users WHERE id = $1",
            user_id
        )
        if row is None:
            return None

        return User(
            row["id"], 
            row["username"]
        )

    async def find_by_name(self, username) -> User:
        row = await fetch_one(
            "SELECT id, username FROM users WHERE username = $1",
            username
        )
        if row is None:
            return None

        return User(
            row["id"], 
            row["username"]
        )
    
    async def find_by_goal(self, goal_id) -> User:
        query = """
            SELECT u.id, u.username
            FROM users u
            JOIN goals g
            ON u.id = g.user_id
            WHERE g.id = $1
        """
        val = await fetch_one(query, goal_id)
        return User(val["id"], val["username"])
        

    async def save(self, user) -> None:
        await execute_query(
            "INSERT INTO users (id, username) VALUES ($1, $2) "
            "ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username",
            user.id,
            user.name
        )

class PgProgressRepository:
    async def add_plan(goal_id, plan_amount, ref_date):
        query = """
            INSERT INTO progress_log (goal_id, plan_amount, date) 
            VALUES ($1, $2, $3)
            ON CONFLICT (goal_id, date) 
            DO UPDATE SET plan_amount = EXCLUDED.plan_amount
        """
        return await execute_query(query, goal_id, plan_amount, ref_date)

    async def add_actual_progress(goal_id, amount, ref_date):
        query = """
            UPDATE progress_log 
            SET actual_amount = COALESCE(actual_amount, 0) + $1 
            WHERE goal_id = $2 AND date = $3
        """
        return await execute_query(query, amount, goal_id, ref_date)
    
    async def fetch_progress(goal_id): # goal_id -> progress
        query = """
            SELECT SUM(actual_amount) 
            FROM progress_log
            WHERE goal_id = $1
        """
        return await fetch_val(query, goal_id)
        
    async def fetch_total_actual_before_today(goal_id, ref_date):
        query = """
            SELECT SUM(actual_amount) 
            FROM progress_log 
            WHERE goal_id = $1 
            AND date < $2
        """
        val = await fetch_val(query, goal_id, ref_date)
        return val if val else 0
    
    async def fetch_weekly_progress_before_today(goal_id, ref_date):
        last_monday = ref_date - timedelta(days=ref_date.weekday())
        query = """
            SELECT SUM(actual_amount) 
            FROM progress_log 
            WHERE goal_id = $1 
            AND date >= $2
            AND date < $3
        """
        val = await fetch_val(query, goal_id, last_monday, ref_date)
        return val if val else 0
    
    async def fetch_daily(user_id, ref_date): # [[名前, 予定, 実績, 現在地], ...]
        query = """
            SELECT 
                g.goal_name, 
                p.plan_amount, 
                p.actual_amount,
                g.start_point,
                COALESCE((
                    SELECT SUM(pl.actual_amount) 
                    FROM progress_log pl 
                    WHERE pl.goal_id = g.id AND pl.date < $1
                ), 0) as total_before
            FROM progress_log p
            JOIN goals g ON p.goal_id = g.id
            WHERE g.user_id = $2
            AND p.date = $1
        """
        return await fetch_all(query, ref_date, user_id)
    
async def make_task_finished(goal_id, ref_date):
    query = """
        UPDATE progress_log
            SET actual_amount = plan_amount
            WHERE goal_id = $1
            AND date = $2;
    """
    return await execute_query(query, goal_id, ref_date)

    
class PgDailyTaskRepository:
    async def _to_dailytask(self, goal_id, user_id, goal_name, plan_amount, actual_amount, is_completed, current_point) -> DailyTask:
        return DailyTask(
            goal_id=goal_id,
            user_id=user_id,
            goal_name=goal_name,
            plan_amount=plan_amount,
            actual_amount=actual_amount,
            is_completed=is_completed,
            current_point=current_point
        )
    
    async def get_dailytasks(self, user_id, ref_date) -> list[DailyTask]:
        query = """
            SELECT 
                g.id,
                g.goal_name,
                p.plan_amount, 
                p.actual_amount,
                cumulative.current_point
            FROM progress_log p
            JOIN goals g ON p.goal_id = g.id
            LEFT JOIN (
                SELECT 
                    goal_id, 
                    COALESCE(SUM(actual_amount), 0) as current_point
                FROM progress_log
                WHERE date < $1
                GROUP BY goal_id
            ) AS cumulative ON g.id = cumulative.goal_id
            WHERE g.user_id = $2 
            AND p.date = $1 
        """
        rows = await fetch_all(query, ref_date, user_id)
        
        tasks = []
        for row in rows:
            try:
                task = await self._to_dailytask(
                    goal_id=row["id"],
                    user_id=user_id,
                    goal_name=row["goal_name"],
                    plan_amount=row["plan_amount"],
                    actual_amount=row["actual_amount"],
                    is_completed=int(row["actual_amount"]) >= int(row["plan_amount"]),
                    current_point=row["current_point"]
                )
                tasks.append(task)
            except DomainError:
                pass    
        return tasks
    
    
class PgDashboardMsgRepository:
    async def update(self, msg_id: int, user_id: int, msg_type: str, goal_id: int = None) -> None:
        if goal_id:
            query = """
                INSERT INTO dashboard_msg 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, msg_type, goal_id) 
                    DO UPDATE SET 
                        msg_id = EXCLUDED.msg_id
            """
        else:
            query = """
                INSERT INTO dashboard_msg 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, msg_type) WHERE goal_id IS NULL
                    DO UPDATE SET 
                        msg_id = EXCLUDED.msg_id
            """
            
        await execute_query(
            query,
            msg_id,
            user_id,
            msg_type,
            goal_id,        
        )

    async def fetch_msgid_by_goal_id(self, goal_id: int, type: str) -> int:
        query = """
            SELECT msg_id
            FROM dashboard_msg
            WHERE goal_id = $1
            AND msg_type = $2
        """
        return await fetch_val(query, goal_id, type)
    
    async def fetch_msgid_by_userid(self, user_id: int, type: str) -> str:
        query = """
            SELECT msg_id
            FROM dashboard_msg
            WHERE user_id = $1
            AND msg_type = $2
        """
        return await fetch_val(query, user_id, type)
    
    async def fetch_user_msgid_list(self, user_id) -> list[int]:
        query = """
            SELECT msg_id
            FROM dashboard_msg
            WHERE user_id = $1
        """
        rows = await fetch_all(query, user_id)
        output = []
        for row in rows:
            output.append(row["msg_id"])
        
        return output
    
    async def delete_row_by_msgid(self, msg_id) -> None:
        query = """
            DELETE
            FROM dashboard_msg
            WHERE msg_id = $1
        """
        return await execute_query(query, msg_id)
        
