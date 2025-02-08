from typing import Optional
from .types import IAgentRuntime, Memory

async def get_providers(
    runtime: IAgentRuntime,
    message: Memory, 
    state: Optional[dict] = None
) -> str:
    """
    Formats provider outputs into a string for context injection.
    
    Args:
        runtime: The AgentRuntime object
        message: The incoming message object
        state: The current state object
        
    Returns:
        String concatenating outputs of each provider
    """
    provider_results = await asyncio.gather(*[
        provider.get(runtime, message, state)
        for provider in runtime.providers
    ])
    
    # Filter out None and empty strings
    filtered_results = [
        result for result in provider_results 
        if result is not None and result != ""
    ]
    
    return "\n".join(filtered_results)