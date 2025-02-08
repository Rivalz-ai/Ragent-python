from typing import List, Optional
from uuid import UUID
import asyncio
from datetime import datetime
from .types import IAgentRuntime, Actor, Memory, Content, Media

async def get_actor_details(runtime: IAgentRuntime, 
                          roomId: UUID) -> List[Actor]:
    """Get details for a list of actors."""
    participant_ids = await runtime.databaseAdapter.getParticipantsForRoom(roomId)
    
    async def get_actor(userId: UUID):
        account = await runtime.databaseAdapter.getAccountById(userId)
        if account:
            return Actor(
                id=account.id,
                name=account.name,
                username=account.username,
                details=account.details
            )
        return None
    
    actors = await asyncio.gather(*[get_actor(uid) for uid in participant_ids])
    return [a for a in actors if a is not None]

def format_actors(actors: List[Actor]) -> str:
    """Format actors into a string."""
    actor_strings = []
    for actor in actors:
        header = f"{actor.name}"
        if actor.details and actor.details.tagline:
            header += f": {actor.details.tagline}"
        if actor.details and actor.details.summary:
            header += f"\n{actor.details.summary}"
        actor_strings.append(header)
    
    return "\n".join(actor_strings)

def format_messages(messages: List[Memory], actors: List[Actor]) -> str:
    """Format messages into a string."""
    def format_msg(message: Memory) -> str:
        if not message.userId:
            return ""
            
        content = message.content
        message_content = content.text
        message_action = content.action
        
        actor = next((a for a in actors if a.id == message.userId), None)
        formatted_name = actor.name if actor else "Unknown User"
        
        attachment_str = ""
        if content.attachments:
            attachments = [
                f"[{m.id} - {m.title} ({m.url})]" 
                for m in content.attachments
            ]
            attachment_str = f" (Attachments: {', '.join(attachments)})"
            
        timestamp = format_timestamp(message.createdAt) if message.createdAt else ""
        short_id = str(message.userId)[-5:]
        
        action_str = f" ({message_action})" if message_action and message_action != "null" else ""
        
        return f"({timestamp}) [{short_id}] {formatted_name}: {message_content}{attachment_str}{action_str}"
    
    message_strings = [
        format_msg(msg) for msg in reversed(messages) 
        if msg.userId
    ]
    
    return "\n".join(msg for msg in message_strings if msg)

def format_timestamp(message_date: float) -> str:
    """Format timestamp into readable string."""
    now = datetime.now().timestamp() * 1000
    diff = now - message_date
    
    abs_diff = abs(diff)
    seconds = int(abs_diff / 1000)
    minutes = int(seconds / 60)
    hours = int(minutes / 60) 
    days = int(hours / 24)
    
    if abs_diff < 60000:
        return "just now"
    elif minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        return f"{days} day{'s' if days != 1 else ''} ago"