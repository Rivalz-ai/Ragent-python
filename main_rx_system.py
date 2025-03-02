# main_rx_system.py
import chainlit as cl
import os
from typing import List
from dotenv import load_dotenv
from multi_agent_orchestrator.orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from multiclass_classifier import OpenAIClassifier, OpenAIClassifierOptions
from in_memory_chat_storage import InMemoryChatStorage 
from agents import create_health_agent, create_travel_agent,create_rx_supervisor, create_default_agent
import uuid
import re
from multi_agent_orchestrator.types import ConversationMessage
import asyncio
from multi_agent_orchestrator.agents import AgentResponse
from supervisor_agent1 import SupervisorAgent
from multi_agent_orchestrator.utils import Logger
# Load environment variables from .env file
load_dotenv()
Logger.info("Environment variables loaded")
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")
def create_classifier():
    Logger.info("Creating classifier")
    classifier = OpenAIClassifier(OpenAIClassifierOptions(
    api_key=DEEP_INFRA_KEY,
    model_id=DEEP_INFRA_MODEL,
    base_url=DEEP_INFRA_URL,
    inference_config={
                    'maxTokens': 500,
                    'temperature': 0.6,
                    'topP': 0.8,
                    'stopSequences': []
                }
    ))
    return classifier

# Create Global storage
shared_storage = InMemoryChatStorage()
Logger.info("Shared storage initialized")
# Create agents
Logger.info("Creating agents...")
custom_classifier = create_classifier()
health_agent = create_health_agent()
travel_agent = create_travel_agent()

default_agent = create_default_agent()
# Create RX Team Supervisor
rx_supervisor = create_rx_supervisor(storage = shared_storage)
Logger.info("All agents created successfully")

# Initialize orchestrator
Logger.info("Initializing orchestrator")
orchestrator = MultiAgentOrchestrator(options=OrchestratorConfig(
        LOG_AGENT_CHAT=True,
        LOG_CLASSIFIER_CHAT=True,
        LOG_CLASSIFIER_RAW_OUTPUT=True,
        LOG_CLASSIFIER_OUTPUT=True,
        LOG_EXECUTION_TIMES=True,
        MAX_RETRIES=3,
        USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED=True,
        MAX_MESSAGE_PAIRS_PER_AGENT=10
    ),
    classifier=custom_classifier,
    default_agent=default_agent,
    storage=shared_storage,
)

# Add all agents
orchestrator.add_agent(rx_supervisor)
orchestrator.add_agent(health_agent)
orchestrator.add_agent(travel_agent)
Logger.info("Agents added to orchestrator")

def generate_start_message(orchestrator: MultiAgentOrchestrator) -> str:
    message = "You are interacting with the following agents:\n"
    for agent_id in orchestrator.agents:
        agent = orchestrator.agents[agent_id]
        if isinstance(agent, SupervisorAgent):
            agent_counts = {}
            for team_agent in agent.team:
                agent_type = type(team_agent).__name__
                if agent_type in agent_counts:
                    agent_counts[agent_type] += 1
                else:
                    agent_counts[agent_type] = 1
            agent_details = "\n".join([f"{agent_type} - Count: {count}" for agent_type, count in agent_counts.items()])
            message += f"- {agent.name} (SupervisorAgent) with the following team:\n{agent_details}\n"
        else:
            message += f"- {agent.name} ({type(agent).__name__})\n"
    return message



def clean_text(extracted_text: str) -> str:
    """Clean the extracted text by removing tags and ensuring only one instance of [AgentName]."""
    # Remove all occurrences of <\startagent> and <\endagent>
    cleaned_text = re.sub(r'<\\startagent>|<\\endagent>', '', extracted_text)
    # Ensure only one instance of [AgentName]
    agent_name_match = re.search(r'\[([^\]]+)\]', cleaned_text)
    if agent_name_match:
        agent_name = agent_name_match.group(0)
        cleaned_text = re.sub(r'\[([^\]]+)\]', '', cleaned_text)
        cleaned_text = agent_name + " " + cleaned_text
    return cleaned_text.strip()


@cl.on_chat_start
async def start():
    Logger.info("New chat session starting")
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    Logger.info(f"Created user_id: {user_id}, session_id: {session_id}")
    cl.user_session.set("chat_history", [])

    start_message = generate_start_message(orchestrator)
    await cl.Message(content=start_message).send()
    Logger.info("Chat session started successfully")



@cl.on_message
async def main(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    Logger.info(f"Processing message for user: {user_id}, session: {session_id}")
    Logger.debug(f"Message content: {message.content[:50]}...")

    msg = cl.Message(content="", author="My Assistant")
    await msg.send()  # Send the message immediately to start streaming
    cl.user_session.set("current_msg", msg)
    try:
        response: AgentResponse = await orchestrator.route_request(message.content, user_id, session_id, {})
        Logger.info(f"Received response from orchestrator for user: {user_id}")
            
    
        # Handle non-streaming responses
        if isinstance(response, AgentResponse) and response.streaming is False:
            raw_output = ""
            
            if isinstance(response.output, str):
                raw_output = response.output
            elif isinstance(response.output, ConversationMessage):
                raw_output = response.output.content[0].get('text', '')

            # Extract messages between <\startagent> and <\endagent>
            extracted_texts = re.findall(r'<\\startagent>(.*?)<\\endagent>', raw_output, re.DOTALL)
            
            if extracted_texts:  
                Logger.info(f"Found {len(extracted_texts)} agent message(s) to process")
                # ✅ Case 1: Found extracted messages → Send each one separately
                for i,extracted_text in enumerate(extracted_texts):
                    cleaned_text = clean_text(extracted_text)
                    author = "My Assistant"
                    if cleaned_text:
                        author = "X Assistant" if "[RX_Agent" in cleaned_text else "My Assistant"
                        if i ==0:
                            msg.author = author
                            await msg.stream_token(cleaned_text)
                            await msg.update()
                            
                        else:
                            sub_msg = cl.Message(content="", author=author)
                            await sub_msg.send()
                            await sub_msg.stream_token(cleaned_text) # Start streaming
                            await sub_msg.update() # Finalize this message # Finalize this message
            else:
                Logger.info("No agent messages found, sending full response")
                # ✅ Case 2: No extracted messages → Send full raw response
                author = "My Assistant"	
                cleaned_text = clean_text(raw_output)
                if "[RX_Agent" in cleaned_text:
                    author = "X Assistant"
                msg.author = author
                await msg.stream_token(cleaned_text)
                await msg.update() # Finalize the message

    except Exception as e:
        Logger.error(f"Error processing message: {e}")
        await msg.stream_token("An error occurred while processing your request. Please try again later.")
        await msg.update()


if __name__ == "__main__":
    cl.run()