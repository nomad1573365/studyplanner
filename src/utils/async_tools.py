import asyncio
import time


class LockEntry:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.last_used = time.time()


locks = {}
TTL = 60 * 10

lock_for_manager = asyncio.Lock()

def get_lock(user_id):
    entry = locks.get(user_id)
    
    if not entry:
        entry = LockEntry()
        locks[user_id] = entry
    
    entry.last_used = time.time()
        
    return entry.lock


async def cleaner():
    while True:
        async with lock_for_manager:
            to_delete = []
            now = time.time()
            for user_id, entry in list(locks.items()):
                if now - entry.last_used > TTL:
                    to_delete.append(user_id)        
            
            for user_id in to_delete:
                locks.pop(user_id, None)
            
        await asyncio.sleep(60)
        