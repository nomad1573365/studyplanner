import models as md
import repository
import db

import math
from datetime import date



def add_daily_task_by_name(user_id, goal_name, amount):
    goal_id = db.fetch_goal_id(user_id, goal_name)
    return repository.add_actual_progress(goal_id, amount)

def record_progress_by_name(user_id, goal_name, amount):
    goal_id = db.fetch_goal_id(user_id, goal_name)
    return repository.record_actual_progress(goal_id, amount)

def get_today_progresses(user_id, date):
    task_list = db.fetch_daily(user_id, date)
    return task_list 

def get_today_schedule():
    pass

def set_weekly_weight(user_id, goal_name, weight):
    if weight < 0:
        return False
    goal_id = db.fetch_goal_id(user_id, goal_name)
    if goal_id is None:
        return False
    return db.update_weekly_weight(goal_id, weight)


def register_habit():
    pass

def check_habit_completion():
    pass

def generate_morning_report():
    pass

def get_weekly_suggestion(user_id, target_date=date.today()): # [[goal_id, goal_name, daily_amount], ...]
    goals = repository.get_user_goal_models(user_id)
    weights = db.fetch_weekly_weights(user_id, target_date)
    suggestion_list = []
    today = date.today()
    
    for goal in goals:
        if goal.is_completed():
            continue
        if goal.is_out_of_period(today):
            continue
            
        weekly_actual_sum = db.fetch_weekly_progress(goal.goal_id)
        weight = weights.get(goal.goal_id, 1.0)
        daily_amount = goal.calculate_daily_amount(weekly_actual_sum, weight)
        if daily_amount is False:
            continue
        suggestion_list.append([goal.goal_id, goal.goal_name, daily_amount])
    return suggestion_list 

def apply_suggestions_to_daily_plan(user_id):
    suggestions = get_weekly_suggestion(user_id)
    
    synced_count = 0
    for goal_id, goal_name, amount in suggestions:
        success = repository.add_daily_plan(user_id, goal_name, amount)
        if success:
            synced_count += 1
                
    return synced_count


