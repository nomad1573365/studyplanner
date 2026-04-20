from src.core import repository as rp, database as db
from src.core.exception import NotFoundError

from datetime import date



async def add_daily_task_by_name(user_id, goal_name, amount):
    return await rp.add_daily_plan(user_id, goal_name, amount)

async def record_progress_by_name(user_id, goal_name, amount, target_date = None):
    goal_id = await db.fetch_goal_id(user_id, goal_name)
    if not target_date:
        target_date = date.today()
    return await rp.record_actual_progress(goal_id, amount, target_date)

async def record_progress_by_id(goal_id, amount, target_date = None):
    if not target_date:
        target_date = date.today()
    return await rp.record_actual_progress(goal_id, amount, target_date)
    
async def get_today_progresses(user_id, date):
    task_list = await db.fetch_daily(user_id, date)
    return task_list 

async def get_today_schedule():
    pass

async def set_weekly_weight(user_id, goal_name, weight):
    if weight < 0:
        return False
    goal_id = await db.fetch_goal_id(user_id, goal_name)
    if goal_id is None:
        return False
    return await db.update_weekly_weight(goal_id, weight, date.today())


async def register_habit():
    pass

async def check_habit_completion():
    pass

async def generate_morning_report():
    pass

async def get_weekly_suggestion(user_id, ref_date):
    goals = await rp.get_user_goal_models(user_id)
    weights_records = await db.fetch_weekly_weights(user_id, ref_date)
    weights = {record['goal_id']: record['weight'] for record in weights_records}
    
    suggestion_list = []
    today = date.today()
    
    for goal in goals:
        if goal.is_completed(): continue
        if goal.is_out_of_period(today): continue
            
        weekly_actual_sum = await db.fetch_weekly_progress_before_today(goal.goal_id, ref_date)

        if weekly_actual_sum is None:
            weekly_actual_sum = 0
            
        weight = float(weights.get(goal.goal_id, 1.0))
        daily_amount = goal.calculate_daily_amount(weekly_actual_sum, today, weight)
        
        if daily_amount is False: continue
        suggestion_list.append([goal.goal_id, goal.goal_name, daily_amount])
        
    return suggestion_list

async def apply_suggestions_to_daily_plan(user_id):
    suggestions = await get_weekly_suggestion(user_id, date.today())
    
    synced_count = 0
    for goal_id, goal_name, amount in suggestions:
        success = await rp.add_daily_plan(user_id, goal_name, amount)
        if success:
            synced_count += 1
                
    return synced_count

async def change_to_date(date_str: str):
    today = date.today()
    if date_str == "today":
        return today
    output = date.strptime(date_str, "%Y-%m-%d")
    return output