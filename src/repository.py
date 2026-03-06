import db
import models as md

from datetime import date, datetime, timedelta
import pandas
import math

today = date.today()

class UserRepository:
    def get_by_id(self, user_id: int):
        row = db.fetch_user_record(user_id)
        if row is None:
            raise ValueError("User not found")
        _, username, created_at = row
        return md.User(user_id, username, created_at)

    def ensure_user(self, username): # -> user_id
        db.add_user(username)
        return db.fetch_user_id(username)

def record_actual_progress(goal_id, actual_amount):
    try:
        db.add_actual_progress(goal_id, actual_amount)
        return True
    except Exception as e:
        print(f"進捗追加に失敗しました: {e}")
        return False
    
def add_daily_plan(user_id, goal_name, plan_amount):
    goal_id = db.fetch_goal_id(user_id, goal_name)
    try:
        db.add_plan(goal_id, plan_amount)
        return True
    except Exception as e:
        print(f"予定追加に失敗しました: {e}")
        return False

def add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
    try:
        goal = md.Goal(user_id, goal_name, start_point, end_point, start_date, end_date)
        db.add_goal(user_id, goal_name, start_point, end_point, start_date, end_date)
        return True
    except:
        return False

def get_user_goal_models(user_id):
    rows = db.fetch_goal_with_progress(user_id)
    output = []
    for row in rows:
        try:
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
        except md.DomainError:
            pass
    return output


def get_user_goal_list(user_id): # [["id", "ゴール名", "開始地点", "終了地点", "開始日", "終了日", "現在地点"], ...]
    goal_list = []
    goal_models = get_user_goal_models(user_id)
    for g in goal_models:
        goal_id, goal_name, start_point, end_point, start_date, end_date, current_point = g.goal_id, g.goal_name, g.start_point, g.end_point, g.start_date, g.end_date, g.current_point
        goal_list.append([goal_id, goal_name, start_point, end_point, start_date, end_date, current_point])
    return goal_list

def delete_user(user_id):
    return db.delete_user(user_id)

def delete_goal(user_id, goal_name):
    goal_id = db.fetch_goal_id(user_id, goal_name) 
    return db.delete_goal(goal_id)




