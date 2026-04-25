import os
from datetime import date, timedelta
from dotenv import load_dotenv

import asyncio
import asyncpg
from src.utils.logger import setup_logger

load_dotenv()
DB_URL = os.environ['DB_URL']
logger = setup_logger(__name__)

pool = None
async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        dsn=DB_URL,
        min_size=1,
        max_size=10,
        statement_cache_size=0,
        max_inactive_connection_lifetime=300.0,
        command_timeout=60.0
        )

def _check_pool():
    if pool is None:
        raise RuntimeError("Database not initialized")

def _query_head(query: str, max_len: int = 200) -> str:
    compact = " ".join(query.split())
    if len(compact) <= max_len:
        return compact
    return compact[:max_len] + "..."

async def execute_query(query, *args):
    """INSERT, UPDATE, DELETE 用"""
    try:
        _check_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)
    except asyncpg.CheckViolationError as e:
        logger.warning(
            f"DB check violation: query='{_query_head(query)}', args={args}, error={e}"
        )
        raise ValueError(str(e)) from e
    except asyncpg.PostgresError as e:
        logger.error(
            f"DB execute failed: query='{_query_head(query)}', args={args}, error={e}",
            exc_info=(type(e), e, e.__traceback__),
        )
        raise
        

async def fetch_one(query, *args):
    """1行取得用"""
    try:
        _check_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    except asyncpg.PostgresError as e:
        logger.error(
            f"DB fetch_one failed: query='{_query_head(query)}', args={args}, error={e}",
            exc_info=(type(e), e, e.__traceback__),
        )
        raise

async def fetch_all(query, *args):
    """全行取得用"""
    try:
        _check_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    except asyncpg.PostgresError as e:
        logger.error(
            f"DB fetch_all failed: query='{_query_head(query)}', args={args}, error={e}",
            exc_info=(type(e), e, e.__traceback__),
        )
        raise

async def fetch_val(query, *args):
    """単一の値（IDやCOUNTなど）取得用"""
    try:
        _check_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
    except asyncpg.PostgresError as e:
        logger.error(
            f"DB fetch_val failed: query='{_query_head(query)}', args={args}, error={e}",
            exc_info=(type(e), e, e.__traceback__),
        )
        raise
