import os
from datetime import date, timedelta
from dotenv import load_dotenv

import asyncio
import asyncpg

load_dotenv()
DB_URL = os.environ['DB_URL']

pool = None
async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        dsn=DB_URL,
        min_size=1,
        max_size=10,
        statement_cache_size=0
        )

def _check_pool():
    if pool is None:
        raise RuntimeError("Database not initialized")

async def execute_query(query, *args):
    """INSERT, UPDATE, DELETE 用"""
    _check_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

async def fetch_one(query, *args):
    """1行取得用"""
    _check_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetch_all(query, *args):
    """全行取得用"""
    _check_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetch_val(query, *args):
    """単一の値（IDやCOUNTなど）取得用"""
    _check_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


#--- 読み込み ---#


async def fetch_user_id(username): # username -> user_id
    query = "SELECT id FROM users WHERE username = $1"
    return await fetch_val(query, str(username))

async def fetch_user_record(user_id): # user_id -> record
    query = "SELECT id, name, created_at FROM users WHERE id = $1"
    return await fetch_one(query, user_id)

async def fetch_goal_id(user_id, goal_name): # user_id, goal_name -> goal_id
    query = "SELECT id FROM goals WHERE goal_name = $1 AND user_id = $2"
    return await fetch_val(query, goal_name, user_id)
        
async def fetch_goal_name(user_id, goal_id): # user_id, goal_name -> goal_id
    query = "SELECT goal_name FROM goals WHERE id = $1 AND user_id = $2"
    return await fetch_val(query, goal_id, user_id)

async def fetch_goal_with_progress(user_id): # user_id -> goal(+progress)
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
        WHERE g.user_id = $1
        GROUP BY g.id
    """
    return await fetch_all(query, user_id)
        
async def fetch_progress(goal_id): # goal_id -> progress
    query = """
        SELECT SUM(actual_amount) 
        FROM progress_log
        WHERE goal_id = $1
    """
    return await fetch_val(query, goal_id)
        
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
        
async def fetch_userlist():
    query = "SELECT id, username FROM users"
    return await fetch_all(query)
        
async def fetch_weekly_progress(goal_id, ref_date):
    last_monday = ref_date - timedelta(days=ref_date.weekday())
    query = "SELECT SUM(actual_amount) FROM progress_log WHERE goal_id = $1 AND date >= $2"
    return await fetch_val(query, goal_id, last_monday)
        
async def fetch_weekly_weights(user_id, ref_date):
    year, week, _ = ref_date.isocalendar()
    query = """
        SELECT goal_id, weight FROM weekly_weights 
        INNER JOIN goals ON weekly_weights.goal_id = goals.id
        WHERE user_id = $1 AND year_num = $2 AND week_num = $3
    """
    return await fetch_all(query, user_id, year, week)


#-- 書き込み --#


async def add_progress(goal_id, actual_amount, ref_date):
    query = """
        INSERT INTO progress_log (goal_id, actual_amount, date)
        SELECT $1, $2, $3
        WHERE EXISTS (
            SELECT 1 FROM plan_amount 
            WHERE goal_id = $4 
            AND date = $5
            AND amount > 0
        )
    """
    return await execute_query(query, goal_id, actual_amount, ref_date, goal_id, ref_date)
    

async def add_actual_progress(goal_id, amount, ref_date):
    query = """
        UPDATE progress_log 
        SET actual_amount = COALESCE(actual_amount, 0) + $1 
        WHERE goal_id = $2 AND date = $3
    """
    return await execute_query(query, amount, goal_id, ref_date)

async def add_plan(goal_id, plan_amount, ref_date):
    query = """
        INSERT INTO progress_log (goal_id, plan_amount, date) 
        VALUES ($1, $2, $3)
        ON CONFLICT (goal_id, date) 
        DO UPDATE SET plan_amount = EXCLUDED.plan_amount
    """
    return await execute_query(query, goal_id, plan_amount, ref_date)

async def add_goal(user_id, goal_name, start_point, end_point, start_date, end_date):
    query = """
        INSERT INTO goals (user_id, goal_name, start_point, end_point, start_date, end_date)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id, goal_name)
        DO UPDATE SET
            start_point = EXCLUDED.start_point,
            end_point = EXCLUDED.end_point,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date
    """
    return await execute_query(query, user_id, goal_name, start_point, end_point, start_date, end_date)

async def add_user(username):
    query = "INSERT INTO users (username) VALUES ($1) ON CONFLICT (username) DO NOTHING"
    return await execute_query(query, username)

async def update_weekly_weight(goal_id, weight, ref_date):
    year, week, _ = ref_date.isocalendar()
    query = """
        INSERT INTO weekly_weights (goal_id, year_num, week_num, weight) 
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (goal_id, year_num, week_num) 
        DO UPDATE SET weight = EXCLUDED.weight
    """
    return await execute_query(query, goal_id, year, week, weight)


#-- 削除 --#


async def delete_user(user_id):
    query = "DELETE FROM users WHERE id = $1"
    return await execute_query(query, user_id)

async def delete_goal(goal_id):
    query = "DELETE FROM goals WHERE id = $1"
    return await execute_query(query, goal_id)

async def delete_weights(goal_id, ref_date):
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
        print(f"ERROR: {e}")

async def delete_last_record(user_id):
    query = """
        DELETE FROM progress_log
        WHERE id = (
            SELECT p.id
            FROM progress_log p
            JOIN goals g ON p.goal_id = g.id
            WHERE g.user_id = $1 AND p.actual_amount != 0 
            ORDER BY p.logged_at DESC, p.id DESC
            LIMIT 1
        )
    """
    try:
        return await execute_query(query, user_id)
    except Exception as e:
        print(f"ERROR: {e}")
