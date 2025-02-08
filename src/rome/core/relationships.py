from typing import List
from uuid import UUID

from .types import IAgentRuntime, Relationship

async def create_relationship(runtime: IAgentRuntime,
                            userA: UUID,  
                            userB: UUID) -> bool:
    """Create relationship between two users"""
    return await runtime.databaseAdapter.createRelationship({
        "userA": userA,
        "userB": userB
    })

async def get_relationship(runtime: IAgentRuntime,
                         userA: UUID,
                         userB: UUID) -> Relationship:
    """Get relationship between two users"""
    return await runtime.databaseAdapter.getRelationship({
        "userA": userA,
        "userB": userB
    })

async def get_relationships(runtime: IAgentRuntime,
                          userId: UUID) -> List[Relationship]:
    """Get all relationships for a user"""
    return await runtime.databaseAdapter.getRelationships({"userId": userId})

async def format_relationships(runtime: IAgentRuntime,
                             userId: UUID) -> List[UUID]:
    """Format relationships for a user"""
    relationships = await get_relationships(runtime, userId)
    
    formatted_relationships = [
        relationship.userB if relationship.userA == userId else relationship.userA 
        for relationship in relationships
    ]
    
    return formatted_relationships