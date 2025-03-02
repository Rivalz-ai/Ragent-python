import uuid
import chainlit as cl
from agents import create_tech_agent, create_travel_agent, create_health_agent,create_X_agent
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multi_agent_orchestrator.classifiers import BedrockClassifier, BedrockClassifierOptions
from multi_agent_orchestrator.classifiers import OpenAIClassifier, OpenAIClassifierOptions
from multi_agent_orchestrator.types import ConversationMessage
from multi_agent_orchestrator.agents import AgentResponse
import os
from dotenv import load_dotenv
from multi_agent_orchestrator.utils import Logger
load_dotenv()

# Initialize the orchestrator
Logger.info("Creating classifier")
custom_openai_classifier = OpenAIClassifier(OpenAIClassifierOptions(
    api_key=os.getenv('OPENAI_API_KEY'),
    model_id='gpt-4o',
    inference_config={
                    'maxTokens': 500,
                    'temperature': 0.5,
                    'topP': 0.8,
                    'stopSequences': []
                }
    ))
Logger.info("Creating orchestrator")
orchestrator = MultiAgentOrchestrator(options=OrchestratorConfig(
        LOG_AGENT_CHAT=True,
        LOG_CLASSIFIER_CHAT=True,
        LOG_CLASSIFIER_RAW_OUTPUT=True,
        LOG_CLASSIFIER_OUTPUT=True,
        LOG_EXECUTION_TIMES=True,
        MAX_RETRIES=3,
        USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED=False,
        MAX_MESSAGE_PAIRS_PER_AGENT=10
    ),
    classifier=custom_openai_classifier
)

# Add agents to the orchestrator
orchestrator.add_agent(create_tech_agent())
orchestrator.add_agent(create_travel_agent())
orchestrator.add_agent(create_health_agent())
orchestrator.add_agent(create_X_agent())
@cl.on_chat_start
async def start():
    cl.user_session.set("user_id", str(uuid.uuid4()))
    cl.user_session.set("session_id", str(uuid.uuid4()))
    cl.user_session.set("chat_history", [])



@cl.on_message
async def main(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    msg = cl.Message(content="")

    await msg.send()  # Send the message immediately to start streaming
    cl.user_session.set("current_msg", msg)

    response:AgentResponse = await orchestrator.route_request(message.content, user_id, session_id, {})


    # Handle non-streaming responses
    if isinstance(response, AgentResponse) and response.streaming is False:
        # Handle regular response
        if isinstance(response.output, str):
            await msg.stream_token(response.output)
        elif isinstance(response.output, ConversationMessage):
                await msg.stream_token(response.output.content[0].get('text'))
    await msg.update()


if __name__ == "__main__":
    cl.run()