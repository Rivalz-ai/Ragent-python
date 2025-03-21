import sys
import os
# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./..")))

from rAgent.agents import AgentCallbacks
from rAgent.agents import OpenAIAgent, OpenAIAgentOptions
from rAgent.ragents import RXAgent, RXAgentOptions
import asyncio
from rAgent.classifiers import OpenAIClassifier, OpenAIClassifierOptions
from rAgent.utils import Logger
import chainlit as cl
from rAgent.ragents.RXRivalz_team import RXTeamSupervisorRivalz, RXTeamSupervisorRivalzOptions
from rAgent.ragents.RX_team import RXTeamSupervisor, RXTeamSupervisorOptions
from backend.utils import read_x_token_yml
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")
auth_key = os.getenv("auth_key")

class ChainlitAgentCallbacks(AgentCallbacks):
    def __init__(self):
        self.is_streaming = False
    def on_llm_new_token(self, token: str) -> None:
        try:
            self.is_streaming = True
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                asyncio.run(cl.user_session.get("current_msg").stream_token(token))
            else:
                # Chỉ sử dụng MỘT trong hai cách sau, không dùng cả hai:
                loop.create_task(cl.user_session.get("current_msg").stream_token(token))
                # KHÔNG gọi cả hai dòng - xóa hoặc comment dòng dưới đây
                # future = asyncio.ensure_future(cl.user_session.get("current_msg").stream_token(token))
        except Exception as e:
            print(f"Error streaming token: {e}")

    def on_llm_end(self) -> None:
        """Called when LLM streaming ends to finalize the message"""
        try:
            if self.is_streaming:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(cl.user_session.get("current_msg").update())
                else:
                    asyncio.run(cl.user_session.get("current_msg").update())
                self.is_streaming = False
        except Exception as e:
            Logger.error(f"Error finalizing message: {e}")

def create_tech_agent():
    options = OpenAIAgentOptions(
            name="Tech Agent",
            description="Specializes in technology areas including software development, hardware, AI, cybersecurity, blockchain, cloud computing, emerging tech innovations, and pricing/costs related to technology products and services.",
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
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
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
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
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
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
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
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
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
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

def create_rx_supervisor(storage = None, num_agents=99):
    lead_agent = OpenAIAgent(OpenAIAgentOptions(
        api_key=OPENAI_API_KEY,
        name="SupervisorAgent",
        description="You a supervisor agent specialized in coordinating X_Agents for social media management (on X). Your role is to orchestrate and oversee the posting and replying activities on Twitter/X platform. You delegate tasks to X_Agents, monitor their performance, and ensure all social media interactions are executed efficiently. You coordinate when and how tweets should be posted or replied to, maintaining a strategic approach to social media engagement.",
        model=OPENAI_MODEL,
        # base_url=DEEP_INFRA_URL,
        inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
        # share_global_memory=True,
        # streaming=True,
    ))
    supervisor = RXTeamSupervisorRivalz(
        RXTeamSupervisorRivalzOptions(
            type="broadcast",
            name="RX_Team_Supervisor",
            description="Manages team of social media posting agents",
            lead_agent=lead_agent,  # Your configured lead agent
            authen_key=auth_key,
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

def create_classifier():
    Logger.info("Creating classifier")
    classifier = OpenAIClassifier(OpenAIClassifierOptions(
    api_key=OPENAI_API_KEY,
    model_id=OPENAI_MODEL,
    # base_url=DEEP_INFRA_URL,
    inference_config={
                    'maxTokens': 500,
                    'temperature': 0.6,
                    'topP': 0.8,
                    'stopSequences': []
                }
    ))
    return classifier



def create_rx_team(storage = None, num_agents=99):
    try:
        lead_agent = OpenAIAgent(OpenAIAgentOptions(
            api_key=OPENAI_API_KEY,
            name="SupervisorAgent",
            description="You a supervisor agent specialized in coordinating X_Agents for social media management (on X). Your role is to orchestrate and oversee the posting and replying activities on Twitter/X platform. You delegate tasks to X_Agents, monitor their performance, and ensure all social media interactions are executed efficiently. You coordinate when and how tweets should be posted or replied to, maintaining a strategic approach to social media engagement.",
            model=OPENAI_MODEL,
            # base_url=DEEP_INFRA_URL,
            inference_config={
                    'maxTokens': 500,
                    'temperature': 0.5,
                    'topP': 0.8,
                    'stopSequences': []
                },
            # share_global_memory=True,
            # streaming=True,
        ))
        x_tokens = read_x_token_yml()['accounts']
        team = []
        for ind, xaccount in enumerate(x_tokens):
            (client_id, client_secret,refresh_token, access_token) = xaccount['name'], xaccount['client_secret'], xaccount['refresh_token'], xaccount['access_token']
            if access_token is not None and access_token != "": 
                agent = RXAgent(RXAgentOptions(
                            name=f"RX_Agent_{ind + 1}",
                            description=(
                                f"Social media (Twitter/X) posting agent #{ind + 1}"
                                " - can post tweets and handle replies."
                            ),
                            api_key=OPENAI_API_KEY,  # Use same OpenAI key as lead agent
                            model=OPENAI_MODEL,  # Use same OpenAI model as lead agent
                            # base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
                            xaccesstoken=access_token,
                            xrefreshtoken=refresh_token,
                            client_secret=client_secret,
                            client_id=client_id,
                            inference_config={
                                'maxTokens': 500,
                                'temperature': 0.5,
                                'topP': 0.8,
                                'stopSequences': []
                            },
                            callbacks=ChainlitAgentCallbacks(),
                            share_global_memory=True,
                        ))
                team.append(agent)
        if len(team) == 0 :
            raise Exception("Not available X_Agents available to create")
        supervisor = RXTeamSupervisor(
            RXTeamSupervisorOptions(
                type="broadcast",
                name="RX_Team_Supervisor",
                description="Manages team of social media posting agents",
                lead_agent=lead_agent,  # Your configured lead agent
                trace=True,
                storage = storage,
                callbacks=ChainlitAgentCallbacks(),
                share_global_memory=True,
                number_of_agents=num_agents,
                team=team
            )
        )

        return supervisor
    except Exception as e:
        Logger.error(f"Error creating RX team: {str(e)}")
        return None