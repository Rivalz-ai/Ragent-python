from rAgent.agents import AgentCallbacks
from openaiAgent import OpenAIAgent, OpenAIAgentOptions
from RXAgent import RXAgent, RXAgentOptions
import asyncio
from tweeter_tool import Xtools
import chainlit as cl
from rx_supervisor import RXTeamSupervisor, RXTeamSupervisorOptions
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")


class ChainlitAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        asyncio.run(cl.user_session.get("current_msg").stream_token(token))

def create_tech_agent():
    options = OpenAIAgentOptions(
            name="Tech Agent",
            description="Specializes in technology areas including software development, hardware, AI, cybersecurity, blockchain, cloud computing, emerging tech innovations, and pricing/costs related to technology products and services.",
            api_key=DEEP_INFRA_KEY,
            model=DEEP_INFRA_MODEL,
            base_url=DEEP_INFRA_URL,
            streaming=True,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=ChainlitAgentCallbacks()
        )
    return OpenAIAgent(options)


def create_default_agent():
    options = OpenAIAgentOptions(
            name="General Agent",
            description="""Default agent for handling general inquiries. Can provide information on a wide range of topics and answer common questions. If no specialized agent is available, this agent will handle the conversation.
            You may be asked about the context related about rAgent of ROME in rival (They are the AI Agents that can interact with resources), here are the context about ROME and rAgent:
            Integration with AI Agents and Identity Verification
Recognizing the growing role of AI agents in decentralized ecosystems, Rome is designed to support and interact with AI agents as first-class participants. The platform's mission is to abstract the complexities of the physical and computational world for AI agents, enabling them to access and utilize resources efficiently.
Romes, the identity verification system, allows users to provide compelling verification through different means. Identity verification plays a crucial role in the reputation system, ensuring that resource provisioning is secure and trustworthy. It also helps limit the amount of resources a single user can supply, preventing botting and sybil attacks, which is essential for maintaining the integrity of interactions involving AI agents.
Users register via Rome, validate themselves, provide resources and receive tokenized versions of those resources in the form of staked tokens.
Additionally, Rome introduces resource mapping for users with verified identities, enabling them to submit information about their technology assets, IoT devices, vehicles, energy resources, for Rome Phase 2 integration.
            """,
            api_key=DEEP_INFRA_KEY,
            model=DEEP_INFRA_MODEL,
            base_url=DEEP_INFRA_URL,
            streaming=True,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=ChainlitAgentCallbacks()
        )
    return OpenAIAgent(options)

def create_travel_agent():
    options = OpenAIAgentOptions(
            name="Travel Agent",
            description="Experienced Travel Agent sought to create unforgettable journeys for clients. Responsibilities include crafting personalized itineraries, booking flights, accommodations, and activities, and providing expert travel advice. Must have excellent communication skills, destination knowledge, and ability to manage multiple bookings. Proficiency in travel booking systems and a passion for customer service required",
            api_key=DEEP_INFRA_KEY,
            model=DEEP_INFRA_MODEL,
            base_url=DEEP_INFRA_URL,
            streaming=True,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=ChainlitAgentCallbacks()
        )
    return OpenAIAgent(options)

def create_health_agent():
    options = OpenAIAgentOptions(
            name="Health Agent",
            description="Specializes in health and wellness, including nutrition, fitness, mental health, and disease prevention. Provides personalized health advice, creates wellness plans, and offers resources for self-care. Must have a strong understanding of human anatomy, physiology, and medical terminology. Proficiency in health coaching techniques and a commitment to promoting overall well-being required.",
            api_key=DEEP_INFRA_KEY,
            model=DEEP_INFRA_MODEL,
            base_url=DEEP_INFRA_URL,
            streaming=True,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=ChainlitAgentCallbacks()
        )
    return OpenAIAgent(options)

def create_X_agent():
    options = RXAgentOptions(
            name="X Agent",
            description="Specializes in twitter (X) areas, you can interact with this agent to post tweets and reply to tweets.",
            api_key=DEEP_INFRA_KEY,
            model=DEEP_INFRA_MODEL,
            base_url=DEEP_INFRA_URL,
            xaccesstoken="U3I4ZVlmSHA1MzhDdmdJb3E3SVMxaHVWYnBPcTZTcWV6RW85aktJUFdUaWxiOjE3Mzk3MzIxODQzNDU6MTowOmF0OjE",
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=ChainlitAgentCallbacks()
        )
    return RXAgent(options)

def create_rx_supervisor(storage = None, num_agents=3):
    lead_agent = OpenAIAgent(OpenAIAgentOptions(
        api_key=DEEP_INFRA_KEY,
        name="SupervisorAgent",
        description="You a supervisor agent specialized in coordinating X_Agents for social media management (on X). Your role is to orchestrate and oversee the posting and replying activities on Twitter/X platform. You delegate tasks to X_Agents, monitor their performance, and ensure all social media interactions are executed efficiently. You coordinate when and how tweets should be posted or replied to, maintaining a strategic approach to social media engagement.",
        model=DEEP_INFRA_MODEL,
        base_url=DEEP_INFRA_URL,
        inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
        # share_global_memory=True,
        # streaming=True,
    ))
    supervisor = RXTeamSupervisor(
        RXTeamSupervisorOptions(
            type="broadcast",
            name="RX_Team_Supervisor",
            description="Manages team of social media posting agents",
            lead_agent=lead_agent,  # Your configured lead agent
            authen_key="1QpEY53il71ZyiHKH",
            trace=True,
            storage = storage,
            callbacks=ChainlitAgentCallbacks(),
            share_global_memory=True,
            number_of_agents=num_agents,
            
        )
    )
    
    # Initialize supervisor and create team
    supervisor.initialize()
    return supervisor