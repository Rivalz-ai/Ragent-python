from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
from typing import Any, Optional, TypeVar, Generic
from uuid import UUID

from .types import ICacheManager, IDatabaseCacheAdapter, CacheOptions


T = TypeVar('T')

class ICacheAdapter(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        pass
        
    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        pass
        
    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

class MemoryCacheAdapter(ICacheAdapter):
    def __init__(self, initial_data: dict = None):
        self.data = initial_data or {}
        
    async def get(self, key: str) -> Optional[str]:
        return self.data.get(key)
        
    async def set(self, key: str, value: str) -> None:
        self.data[key] = value
        
    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

class FsCacheAdapter(ICacheAdapter):
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        
    async def get(self, key: str) -> Optional[str]:
        try:
            path = self.data_dir / key
            return await path.read_text()
        except:
            return None
            
    async def set(self, key: str, value: str) -> None:
        try:
            path = self.data_dir / key
            path.parent.mkdir(parents=True, exist_ok=True)
            await path.write_text(value)
        except Exception as e:
            print(f"Cache write error: {e}")
            
    async def delete(self, key: str) -> None:
        try:
            path = self.data_dir / key
            path.unlink(missing_ok=True)
        except:
            pass

class DbCacheAdapter(ICacheAdapter):
    def __init__(self, db: IDatabaseCacheAdapter, agent_id: UUID):
        self.db = db
        self.agent_id = agent_id
        
    async def get(self, key: str) -> Optional[str]:
        return await self.db.getCache(self.agent_id, key)
        
    async def set(self, key: str, value: str) -> None:
        await self.db.setCache(self.agent_id, key, value)
        
    async def delete(self, key: str) -> None:
        await self.db.deleteCache(self.agent_id, key)

class CacheManager(Generic[T], ICacheManager):
    def __init__(self, adapter: ICacheAdapter):
        self.adapter = adapter
        
    async def get(self, key: str) -> Optional[T]:
        data = await self.adapter.get(key)
        if data:
            parsed = json.loads(data)
            if not parsed['expires'] or parsed['expires'] > time.time():
                return parsed['value']
            await self.delete(key)
        return None
            
    async def set(self, key: str, value: T, opts: Optional[CacheOptions] = None) -> None:
        data = {
            'value': value,
            'expires': opts.expires if opts else 0
        }
        await self.adapter.set(key, json.dumps(data))
        
    async def delete(self, key: str) -> None:
        await self.adapter.delete(key)