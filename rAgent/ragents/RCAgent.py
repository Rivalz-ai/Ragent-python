from rAgent.agents.agent import Agent, AgentOptions
from rAgent.types import ConversationMessage
from typing import Dict, List, Optional, Any, Union, AsyncIterable

class ComputeAgent(Agent):
    def __init__(self, options: AgentOptions):
        super().__init__(options)
        self.description = "Agent that interacts with compute resources (execute code, execute URL commands, perform computations, provide system information)."

    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> Union[ConversationMessage, AsyncIterable[Any]]:
        # Implement logic to handle compute resource tasks
        # This is a placeholder implementation
        response_text = f"ComputeAgent received your request: {input_text}"
        return ConversationMessage(
            sender=self.name,
            content=response_text,
            metadata={}
        )
