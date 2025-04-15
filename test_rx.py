import uuid
import chainlit as cl
import os
from dotenv import load_dotenv

# Import RXAgent
from rAgent.ragents import RXAgent, RXAgentOptions
from rAgent.types import ConversationMessage
from rAgent.agents import AgentCallbacks
import asyncio
class ChainlitAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        asyncio.run(cl.user_session.get("current_msg").stream_token(token))

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")
# Create RXAgent
def create_X_agent(access_token, refresh_token, client_secret, client_id):
    if access_token != "" and access_token is not None:
        return RXAgent(RXAgentOptions(
                            name=f"RX_Agent",
                            description=(
                                f"Social media (Twitter/X) posting agent ##"
                                " - can post tweets and handle replies."
                                "- If user asks the normal question, please answer it normaly."
                            ),
                            api_key=OPENAI_API_KEY,  # Use same OpenAI key as lead agent
                            model=OPENAI_MODEL,  # Use same OpenAI model as lead agent
                            # base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
                            xaccesstoken=access_token,
                            xrefreshtoken=refresh_token, ## optional
                            client_secret=client_secret,## optional
                            client_id=client_id,## optional
                            inference_config={
                                'maxTokens': 500,
                                'temperature': 0.5,
                                'topP': 0.8,
                                'stopSequences': []
                            },
                            callbacks=ChainlitAgentCallbacks(),
                        ))
    else:
        raise ValueError("Access token is required to create X agent")

agent = create_X_agent(access_token="SUlqcUdpamgtTzBCcjRxbzV1RTIybXZGNWttVlN4ZHBrVUpNTm5paFBtVGlQOjE3NDE5OTE5MDcwNjA6MToxOmF0OjE", refresh_token="", client_secret="", client_id="")

@cl.on_chat_start
async def start():
    cl.user_session.set("user_id", str(uuid.uuid4()))
    cl.user_session.set("session_id", str(uuid.uuid4()))

@cl.on_message
async def handle_message(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    msg = cl.Message(content="")
    await msg.send()
    cl.user_session.set("current_msg", msg)

    response = await agent.process_request(
        input_text=message.content,
        user_id=user_id,
        session_id=session_id,
        chat_history=[]
    )

    if isinstance(response, ConversationMessage):
        await msg.stream_token(response.content[0]["text"])

    await msg.update()

# Run Chainlit server
if __name__ == "__main__":
    cl.run()