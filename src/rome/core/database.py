from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from uuid import UUID

from .types import (
    Account, Actor, Goal, Memory, Relationship, 
    GoalStatus, Participant, IDatabaseAdapter
)
from .database.circuit_breaker import CircuitBreaker
from .logger import rome_logger

class DatabaseAdapter(IDatabaseAdapter, ABC):
    """Abstract database adapter with circuit breaker pattern"""
    
    def __init__(self, circuit_breaker_config: Optional[Dict] = None):
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_config.get('failure_threshold', 5),
            reset_timeout=circuit_breaker_config.get('reset_timeout', 60000),
            half_open_max_attempts=circuit_breaker_config.get('half_open_max_attempts', 3)
        )
        self.db = None

    async def with_circuit_breaker(self, operation, context: str):
        """Execute operation with circuit breaker protection"""
        try:
            return await self.circuit_breaker.execute(operation)
        except Exception as error:
            rome_logger.error(f"Circuit breaker error in {context}:", {
                "error": str(error),
                "state": self.circuit_breaker.get_state()
            })
            raise

    @abstractmethod
    async def init(self) -> None:
        """Initialize database connection"""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close database connection"""
        raise NotImplementedError

    @abstractmethod
    async def get_account_by_id(self, user_id: UUID) -> Optional[Account]:
        """Get account by ID"""
        raise NotImplementedError

    @abstractmethod
    async def create_account(self, account: Account) -> bool:
        """Create new account"""
        raise NotImplementedError

    @abstractmethod
    async def get_memories(self, params: Dict) -> List[Memory]:
        """Get memories with parameters"""
        raise NotImplementedError

    @abstractmethod
    async def get_memories_by_room_ids(self, params: Dict) -> List[Memory]:
        """Get memories for multiple rooms"""
        raise NotImplementedError

    @abstractmethod  
    async def search_memories(self, params: Dict) -> List[Memory]:
        """Search memories by embedding"""
        raise NotImplementedError

    @abstractmethod
    async def create_memory(self, memory: Memory, table_name: str, unique: bool = False) -> None:
        """Create new memory"""
        raise NotImplementedError

    @abstractmethod
    async def get_goals(self, params: Dict) -> List[Goal]:
        """Get goals with parameters"""
        raise NotImplementedError

    @abstractmethod
    async def update_goal(self, goal: Goal) -> None:
        """Update existing goal"""
        raise NotImplementedError

    @abstractmethod
    async def create_goal(self, goal: Goal) -> None:
        """Create new goal"""
        raise NotImplementedError

    @abstractmethod
    async def get_room(self, room_id: UUID) -> Optional[UUID]:
        """Get room by ID"""
        raise NotImplementedError

    @abstractmethod
    async def create_room(self, room_id: Optional[UUID] = None) -> UUID:
        """Create new room"""
        raise NotImplementedError

    @abstractmethod
    async def get_participants_for_room(self, room_id: UUID) -> List[UUID]:
        """Get room participants"""
        raise NotImplementedError

    @abstractmethod
    async def create_relationship(self, params: Dict) -> bool:
        """Create relationship between users"""
        raise NotImplementedError

    @abstractmethod
    async def get_relationships(self, params: Dict) -> List[Relationship]:
        """Get relationships for user"""
        raise NotImplementedError