from src.core import models as md
from abc import ABC, abstractmethod
from src.core.models import Goal, User, DailyTask
from src.core.exception import NotFoundError, DomainError
from src.utils.logger import setup_logger

from datetime import date, datetime, timedelta
import pandas
import math

today = date.today()
logger = setup_logger(__name__)

from src.core.database import fetch_all, fetch_val, fetch_one, execute_query

class PgGoalRepository:    
    async def find_by_id(self, goal_id) -> Goal:
        row = await fetch_one(
            "SELECT * FROM goals WHERE id = $1",
            goal_id
        )
        if row is None:
            raise NotFoundError("指定のゴールが見つかりませんでした。")

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
        
    async def create(self, goal: Goal) -> int:
        new_id = await fetch_val(
            """
            INSERT INTO goals (user_id, goal_name, start_point, end_point, start_date, end_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            goal.user_id, goal.goal_name, goal.start_point, goal.end_point, goal.start_date, goal.end_date
        )
        return new_id
        
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
        if val is None:
            raise NotFoundError("指定のゴールが見つかりませんでした。")
        return User(val["id"], val["username"])
        

    async def save(self, user: User) -> None:
        await execute_query(
            "INSERT INTO users (id, username) VALUES ($1, $2) "
            "ON CONFLICT (id) DO UPDATE SET username = EXCLUDED.username",
            user.id,
            user.name
        )
    
    async def create(self, username) -> int:
        query = "INSERT INTO users (username) VALUES ($1) ON CONFLICT (username) DO NOTHING RETURNING id"
        return await fetch_val(query, username)
    
    async def delete(self, user: User) -> None:
        query = "DELETE FROM users WHERE id = $1"
        return await execute_query(query, user.id)
    
    async def fetch_active_userlist(self, within_date, ref_date=None):
        if ref_date is None:
            ref_date = date.today()

        target_date = ref_date - timedelta(days=within_date)

        query = """
            SELECT DISTINCT u.id FROM users u
            JOIN goals g ON u.id = g.user_id
            LEFT JOIN progress_log p ON g.id = p.goal_id
            WHERE p.date >= $1
            OR g.start_date >= $1
        """
        return await fetch_all(query, target_date)
        

class PgProgressRepository:
    async def add_plan(self, goal_id, plan_amount, ref_date):
        query = """
            INSERT INTO progress_log (goal_id, plan_amount, date) 
            VALUES ($1, $2, $3)
            ON CONFLICT (goal_id, date) 
            DO UPDATE SET plan_amount = EXCLUDED.plan_amount
        """
        return await execute_query(query, goal_id, plan_amount, ref_date)

    async def add_actual_progress(self, goal_id, amount, ref_date):
        query = """
            UPDATE progress_log 
            SET actual_amount = COALESCE(actual_amount, 0) + $1 
            WHERE goal_id = $2 AND date = $3
        """
        return await execute_query(query, amount, goal_id, ref_date)
    
    async def fetch_progress(self, goal_id):
        query = """
            SELECT SUM(actual_amount) 
            FROM progress_log
            WHERE goal_id = $1
        """
        return await fetch_val(query, goal_id)
        
    async def fetch_total_actual_before_today(self, goal_id, ref_date):
        query = """
            SELECT SUM(actual_amount) 
            FROM progress_log 
            WHERE goal_id = $1 
            AND date < $2
        """
        val = await fetch_val(query, goal_id, ref_date)
        return val if val else 0
    
    async def fetch_weekly_progress_before_today(self, goal_id, ref_date):
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
    
    async def fetch_daily(self, user_id, ref_date): # [[名前, 予定, 実績, 現在地], ...]
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
            AND g.start_date <= $1
            AND g.end_date >= $1
        """
        return await fetch_all(query, ref_date, user_id)

    async def make_task_finished(self, goal_id, ref_date):
        query = """
            UPDATE progress_log
                SET actual_amount = plan_amount
                WHERE goal_id = $1
                AND date = $2;
        """
        return await execute_query(query, goal_id, ref_date)

    
class PgDailyTaskRepository:
    async def _to_dailytask(
        self,
        goal_id,
        user_id,
        goal_name,
        plan_amount,
        actual_amount,
        is_completed,
        current_point,
        goal_start_point,
    ) -> DailyTask:
        return DailyTask(
            goal_id=goal_id,
            user_id=user_id,
            goal_name=goal_name,
            plan_amount=plan_amount,
            actual_amount=actual_amount,
            is_completed=is_completed,
            current_point=current_point,
            goal_start_point=goal_start_point,
        )
    
    async def get_dailytasks(self, user_id, ref_date) -> list[DailyTask]:
        query = """
            SELECT 
                g.id,
                g.goal_name,
                g.start_point,
                p.plan_amount, 
                p.actual_amount,
                COALESCE((
                    SELECT SUM(pl.actual_amount)
                    FROM progress_log pl
                    WHERE pl.goal_id = g.id
                    AND pl.date < $1
                ), 0) as current_point
            FROM progress_log p
            JOIN goals g ON p.goal_id = g.id
            WHERE g.user_id = $2 
            AND p.date = $1
            AND g.start_date <= $1
            AND g.end_date >= $1
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
                    current_point=row["current_point"],
                    goal_start_point=row["start_point"]
                )
                tasks.append(task)
            except DomainError as e:
                logger.warning(
                    f"DailyTask conversion skipped: user_id={user_id}, goal_id={row.get('id')}, "
                    f"plan={row.get('plan_amount')}, actual={row.get('actual_amount')}, "
                    f"current_point={row.get('current_point')}, error={e}"
                )
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
        
        
class PgWeeklyWeightRepository:
    async def fetch_weights(self, user_id, ref_date):
        year, week, _ = ref_date.isocalendar()
        query = """
            SELECT goal_id, weight FROM weekly_weights 
            INNER JOIN goals ON weekly_weights.goal_id = goals.id
            WHERE user_id = $1 AND year_num = $2 AND week_num = $3
        """
        return await fetch_all(query, user_id, year, week)
    
    async def update(self, goal_id, weight, ref_date):
        year, week, _ = ref_date.isocalendar()
        query = """
            INSERT INTO weekly_weights (goal_id, year_num, week_num, weight) 
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (goal_id, year_num, week_num) 
            DO UPDATE SET weight = EXCLUDED.weight
        """
        return await execute_query(query, goal_id, year, week, weight)
    
    async def delete_weights(self, goal_id, ref_date):
        year, week, _ = ref_date.isocalendar()
        query = """
            DELETE FROM weekly_weights 
            WHERE goal_id = $1
              AND year_num = $2 
              AND week_num = $3
        """
        try:
            return await execute_query(query, goal_id, year, week)
        except Exception as e:
            logger.error(
                f"delete_weights failed: goal_id={goal_id}, year={year}, week={week}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )
            raise

