from rAgent.agents.agent import Agent, AgentOptions
from rAgent.types import ConversationMessage
from typing import Dict, List, Optional, Any, Union, AsyncIterable

class REAgent(Agent):
    def __init__(self, options: AgentOptions):
        super().__init__(options)
        self.description = "Agent that interacts with Linux systems (execute commands, perform curls, build Docker images, fix bugs)."

    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> Union[ConversationMessage, AsyncIterable[Any]]:
        # Implement logic to handle execution tasks
        # This is a placeholder implementation
        response_text = f"ExecuteAgent received your request: {input_text}"
        return ConversationMessage(
            sender=self.name,
            content=response_text,
            metadata={}
        )
