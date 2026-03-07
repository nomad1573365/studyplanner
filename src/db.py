import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
DB_PASSWORD = os.environ['DB_PASSWORD']
db_url = f"postgresql://postgres.rdtbxxyivsvmjzfqdrza:{DB_PASSWORD}@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"

def get_connection():
    return psycopg2.connect(db_url, cursor_factory=DictCursor)

#--- 読み込み ---#

def fetch_user_id(username): # username -> user_id
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (str(username),))
            res = cur.fetchone()
            return res["id"] if res else None
        
def fetch_user_record(user_id): # user_id -> record
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, created_at FROM users WHERE id = %s", (str(user_id),))
            res = cur.fetchone()
            return res

def fetch_goal_id(user_id, goal_name): # user_id, goal_name -> goal_id
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM goals WHERE goal_name = %s AND user_id = %s", (goal_name, user_id))
            res = cur.fetchone()
            return res["id"] if res else None
        
def fetch_goal_name(user_id, goal_id): # user_id, goal_name -> goal_id
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT goal_name FROM goals WHERE goal_id = %s AND user_id = %s", (goal_id, user_id))
            res = cur.fetchone()
            return res["goal_name"] if res else None

def fetch_goal_with_progress(user_id): # user_id -> goal(+progress)
    query ="""
        SELECT 
            g.id,
            g.goal_name,
            g.start_point,
            g.end_point,
            g.start_date,
            g.end_date,
            COALESCE(SUM(p.actual_amount), 0) as current_point,
            g.end_point - g.start_point + 1 as total_amount,
            g.end_date - CURRENT_DATE as days_left
        FROM goals g
        LEFT JOIN progress_log p ON g.id = p.goal_id
        WHERE g.user_id = %s
        GROUP BY g.id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            return cur.fetchall()
        
def fetch_progress(goal_id): # goal_id -> progress
    query = """
        SELECT SUM(amount) 
        FROM progress_log
        WHERE goal_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id,))
            return cur.fetchone()
        
def fetch_daily(user_id, ref_date): # [[名前, 予定, 実績, 現在地], ...]
    # progress_log と goals を結合して、ユーザーIDで絞り込む
    query = query = """
        SELECT 
            g.goal_name, 
            p.plan_amount, 
            p.actual_amount,
            g.start_point,
            -- 今日の日付(target_date)より前の累計実績を計算
            COALESCE((
                SELECT SUM(pl.actual_amount) 
                FROM progress_log pl 
                WHERE pl.goal_id = g.id AND pl.date < %s
            ), 0) as total_before
        FROM progress_log p
        JOIN goals g ON p.goal_id = g.id
        WHERE g.user_id = %s
          AND p.date = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (ref_date, user_id, ref_date))
            return cur.fetchall() 
        
def fetch_userlist():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username FROM users")
            return cur.fetchall()
        
def fetch_weekly_progress(goal_id):
    today = date.today()
    last_monday = today - timedelta(days=today.weekday())
    
    query = "SELECT SUM(actual_amount) FROM progress_log WHERE goal_id = %s AND date >= %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id, last_monday))
            res = cur.fetchone()
            return res[0] if res[0] is not None else 0
        
def fetch_weekly_weights(user_id, ref_date=date.today()):
    year, week, _ = ref_date.isocalendar()
    query = """
        SELECT goal_id, weight FROM weekly_weights 
        INNER JOIN goals ON weekly_weights.goal_id = goals.id
        WHERE user_id = %s AND year_num = %s AND week_num = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, year, week))
            rows = cur.fetchall()
            return {row['goal_id']: row['weight'] for row in rows}

#-- 書き込み --#

def add_progress(goal_id, actual_amount, ref_date=date.today()):
    query = """
        INSERT INTO progress_log (goal_id, actual_amount, date)
        SELECT %s, %s, %s
        WHERE EXISTS (
            SELECT 1 FROM plans 
            WHERE goal_id = %s 
            AND date = %s 
            AND amount > 0
        )
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id, actual_amount, ref_date, goal_id, ref_date))
            conn.commit()
            return True
    return False

def add_actual_progress(goal_id, amount):
    query = """
        UPDATE progress_log 
        SET actual_amount = COALESCE(actual_amount, 0) + %s 
        WHERE goal_id = %s AND date = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (amount, goal_id, date.today()))
            conn.commit()
            return cur.rowcount > 0
    return False

def add_plan(goal_id, plan_amount):
    query = """
        INSERT INTO progress_log (goal_id, plan_amount, date) 
        VALUES (%s, %s, %s)
        ON CONFLICT (goal_id, date) 
        DO UPDATE SET plan_amount = EXCLUDED.plan_amount
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id, plan_amount, date.today()))
            conn.commit()
            return True
    return False

def add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
    query = """
        INSERT INTO goals (user_id, goal_name, start_point, end_point, start_date, end_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, goal_name)
        DO UPDATE SET
            start_point = EXCLUDED.start_point,
            end_point = EXCLUDED.end_point,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, goal_name, start_point, end_point, start_date, end_date))
            conn.commit()
            return True
    return False

def add_user(username):
    query = "INSERT INTO users (username, created_at) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (username, date.today()))
            conn.commit()
            return True
    return False

def update_weekly_weight(goal_id, weight, ref_date=date.today()):
    today = ref_date
    year, week, _ = today.isocalendar()
    query = """
        INSERT INTO weekly_weights (goal_id, year_num, week_num, weight) 
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (goal_id, year_num, week_num) 
        DO UPDATE SET weight = EXCLUDED.weight
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id, year, week, weight))
            conn.commit()
            return True
    return False

#-- 削除 --#

def delete_user(user_id):
    query = "DELETE FROM users WHERE id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            conn.commit()
            return True
    return False

def delete_goal(goal_id):
    query = "DELETE FROM goals WHERE id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (goal_id,))
            conn.commit()
            return True
    return False

def delete_weights(goal_id, ref_date=date.today()):
    year, week, _ = ref_date.isocalendar()
    query = """
        DELETE FROM weekly_weights 
        WHERE goal_id = %s
          AND year_num = %s 
          AND week_num = %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (goal_id, year, week))
                conn.commit()
                return True
    except Exception as e:
        print(f"ERROR: {e}")
        pass
    