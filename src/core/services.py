from src.core import repository as rp
from src.core.exception import DomainError, NotFoundError
from src.utils.logger import setup_logger
from src.core.models import *

from datetime import date, timedelta


logger = setup_logger(__name__)



async def add_daily_task_by_name(user_id, goal_name, amount, target_date = None):
    if not target_date:
        target_date = date.today()
    return await rp.PgProgressRepository().add_plan(user_id, goal_name, amount)

async def record_progress_by_name(user_id, goal_name, amount, target_date = None):
    goal = await rp.PgGoalRepository().find_by_name(user_id, goal_name)
    if not target_date:
        target_date = date.today()
    return await rp.PgProgressRepository().add_actual_progress(goal.goal_id, amount, target_date)

async def record_progress_by_id(goal_id, amount, target_date = None):
    if not target_date:
        target_date = date.today()
    return await rp.PgProgressRepository().add_actual_progress(goal_id, amount, target_date)

async def set_weekly_weight(user_id, goal_name, weight):
    if weight <= 0:
        raise ValueError("重み付けは正の値にしてください。")
    goal = await rp.PgGoalRepository().find_by_name(user_id, goal_name)
    if goal.goal_id is None:
        raise NotFoundError("指定されたゴールは見つかりませんでした。")
    return await rp.PgWeeklyWeightRepository().update(goal.goal_id, weight, date.today())

async def get_weekly_suggestion(user_id, ref_date):
    goals = await rp.PgGoalRepository().find_by_user(user_id)
    weights_records = await rp.PgWeeklyWeightRepository().fetch_weights(user_id, date.today())
    weights = {record['goal_id']: record['weight'] for record in weights_records}
    
    suggestion_list = []
    for goal in goals:
        if goal.is_completed(): continue
        if goal.is_out_of_period(ref_date): continue
            
        weekly_actual_sum = await rp.PgProgressRepository().fetch_weekly_progress_before_today(goal.goal_id, ref_date)
        

        if weekly_actual_sum is None:
            weekly_actual_sum = 0
            
        weight = float(weights.get(goal.goal_id, 1.0))
        daily_amount = goal.calculate_daily_amount(weekly_actual_sum, ref_date, weight)
        
        if daily_amount is False: continue
        suggestion_list.append([goal.goal_id, goal.goal_name, daily_amount])
        
    return suggestion_list

async def apply_suggestions_to_daily_plan(user_id):
    suggestions = await get_weekly_suggestion(user_id, date.today())
    
    for goal_id, goal_name, amount in suggestions:
        try:
            if amount is None or int(amount) <= 0:
                continue
            await rp.PgProgressRepository().add_plan(goal_id, amount, date.today())

        except DomainError as e:
            logger.warning(
                f"Skip suggestion sync due to domain error: user_id={user_id}, "
                f"goal_id={goal_id}, goal_name={goal_name}, amount={amount}, error={e}"
            )
        except Exception as e:
            logger.error(
                f"Suggestion sync failed: user_id={user_id}, goal_id={goal_id}, "
                f"goal_name={goal_name}, amount={amount}, error={e}",
                exc_info=(type(e), e, e.__traceback__),
            )

def change_to_date(date_str: str):
    today = date.today()
    normalized = str(date_str).strip().lower()
    if normalized == "today" or normalized == "":
        return today
    elif normalized == "tomorrow":
        return today + timedelta(days=1)
    elif normalized.isdigit():
        days = int(normalized)
        if days < 0:
            raise ValueError("日数は正の値にしてください。")
        return today + timedelta(days=int(normalized))
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d",):
        try:
            return date.strptime(normalized, fmt)
        except ValueError:
            logger.info(f"Invalid date format received: {date_str}")
            raise DomainError("日付が不正です。MM-DD、YYYY-MM-DD（またはスラッシュ）のように記入してください。")



async def ensure_user(username):
    user = await rp.PgUserRepository().find_by_name(username)
    if not user:
        user_id = await rp.PgUserRepository().create(username)
        user = User(user_id, username)
    return user