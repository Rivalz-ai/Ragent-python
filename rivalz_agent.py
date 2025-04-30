import os
import uuid
from typing import Dict, Optional, Union, List, Any
import logging
import asyncio
import aiohttp
from dotenv import load_dotenv
from rAgent.agents import (Agent,
                        AgentResponse,
                        AgentProcessingResult)
# Import agent types and options
from rAgent.ragents import RCAgent, RCAgentOptions
from rAgent.ragents import RDAgent, RDAgentOptions
from rAgent.ragents import RXRivalzAgent, RXAgentRivalzOptions

from rAgent.ragents import REAgent, REAgentOptions 
from rAgent.types import ConversationMessage
from rAgent.agents import AgentCallbacks, AgentResponse, Agent
from rAgent.utils import Logger
from rAgent.storage import InMemoryChatStorage
import httpx
from datetime import datetime


from rAgent.orchestrator import SwarmOrchestrator, OrchestratorConfig
from rAgent.storage import InMemoryChatStorage
from backend.agents import create_health_agent, create_travel_agent, create_rx_supervisor, create_default_agent,create_classifier 
# Load environment variables
load_dotenv()
import chainlit as cl

from rAgent.agents import AgentCallbacks

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



class RivalzAgent:
    """
    Unified agent class that manages different Rivalz agent types (RC, RD, RE, RX)
    and provides a consistent interface for interaction with these agents.
    """
    
    def __init__(self, project_id: str, shared_storage: InMemoryChatStorage):
        """
        Initialize the RivalzAgent with specified project ID and agent types.
        
        Args:
            project_id (str): The project identifier for authentication
            agent_types (List[str], optional): List of agent types to initialize. 
                                              Options: "rc", "rd", "re", "rx"
        """
        # Load configuration
        self.project_id = project_id
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.deep_infra_key = os.getenv("deep_infra_api_key")
        self.deep_infra_url = os.getenv("base_url")
        self.deep_infra_model = os.getenv("deep_infra_model")
        self.rivalz_url = os.getenv("RIVAL_URL", "https://staging-rome-api-v2.rivalz.ai/agent")
        self.project_auth_token = os.getenv("auth_key", project_id)
        self.callbacks =ChainlitAgentCallbacks()
        self.shared_storage = shared_storage
        self.team_info = {}
        # Initialize storage
        # Removed calls to _fetch_resource_info and _initialize_agent

    async def initialize(self):
        """Initialize the agent asynchronously"""
        await self._fetch_resource_info()
        await self._initialize_agent()
        return self

    @classmethod
    async def create(cls, project_id, shared_storage):
        """Factory method to create and initialize RivalzAgent"""
        agent = cls(project_id, shared_storage)
        await agent._fetch_resource_info()
        await agent._initialize_agent()
        return agent

    async def _fetch_resource_info(self):
        """
        Fetch available agent types from the API and initialize them.
        """
        try:
            params = {'authen_key': self.project_auth_token, 'project_id': self.project_id}
            api_url = f"{self.rivalz_url}/agent/swarm"
            Logger.info(f"Fetching team info from API at {api_url}")
            
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(api_url, params=params)
                
            if response.status_code != 200:
                Logger.error(f"Error fetching team info: {response.status_code} - {response.text}")
                return {}
                
            data = response.json()
            resources = data.get('data', {}).get('resources', {})
            
            # Update team info
            self.team_info = {
                'info': data.get('data', {}).get('info', {}),
                'rx': resources.get('rx', 0),
                'rc': resources.get('rc', 0),
                'rd': resources.get('rd', 0),
                're': resources.get('re', 0), # Added REAgent case
                'total_resources': resources.get('total', 0),
                'last_updated': datetime.now()
            }
            
        except Exception as e:

            Logger.error(f" Error fetching team info: {str(e)}")
            self.team_info = {}    
    
    async def _initialize_agent(self):
        """Initialize agent types based on available resources in team_info."""
        if not self.team_info:
            Logger.error("Team info not available. Cannot initialize agents.")
            raise ValueError("Team info not available. Cannot initialize agents.")
        
        self.polling_tasks = {}
        self.polling_active = False
        
        agent_configs = {
            'rc': {'attr': 'rc_agent', 'creator': self._create_rc_agent, 'name': 'RC'},
            'rd': {'attr': 'rd_agent', 'creator': self._create_rd_agent, 'name': 'RD'},
            're': {'attr': 're_agent', 'creator': self._create_re_agent, 'name': 'RE'},
            'rx': {'attr': 'rx_agent', 'creator': self._create_rx_agent, 'name': 'RX'}
        }

        for agent_type, config in agent_configs.items():
            try:
                if self.team_info.get(agent_type, 0) > 0:
                    if agent_type == 'rx':
                        # Await the async creation of RX agent
                        agent = await config['creator']()
                    else:
                        # Other agents are synchronous
                        numberagent = self.team_info.get(agent_type, 0)
                        agent = config['creator'](numberagent)
                    setattr(self, config['attr'], agent)
                    Logger.info(f"{config['name']} Agent Initialized with {self.team_info.get(agent_type, 0)} instances")
                else:
                    setattr(self, config['attr'], None)
            except Exception as e:
                Logger.error(f"Failed to initialize {config['name']} Agent: {str(e)}")
                setattr(self, config['attr'], None)

    def _create_rc_agent(self, numberagent) -> RCAgent:
        """Create and configure a Resource Compute (RC) agent"""
        return RCAgent(RCAgentOptions(
            name="RC_Agent",
            description=(
                "Compute Resource Agent specialized in system monitoring, "
                "command execution, and resource management. "
                "Can perform health checks, monitor resources, and execute safe commands."
                f"You are control {numberagent} instance RC in this swarm."
            ),
            api_key=self.api_key,
            model=self.openai_model,
            project_auth_token=self.project_auth_token,
            project_id=self.project_id,
            api_base_url=self.rivalz_url,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=self.callbacks,
            streaming = False,
        ))
    
    def _create_rd_agent(self, numberagent) -> RDAgent:
        """Create and configure a Resource Data (RD) agent"""
        return RDAgent(RDAgentOptions(
            name="RD_Agent",
            description=(
                "Data Resource Agent specialized in data fetching, monitoring, and processing. "
                "Can perform URL checks, periodic data retrieval, file operations, and data transformations. "
                f"You are control {numberagent} instance RD in this swarm."
            ),
            api_key=self.api_key,
            model=self.openai_model,
            project_auth_token=self.project_auth_token,
            project_id=self.project_id,
            api_base_url=self.rivalz_url,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
                'topP': 0.8,
                'stopSequences': []
            },
            callbacks=self.callbacks,
            streaming = False,
        ))
    
    def _create_re_agent(self, numberagent) -> REAgent:
        """Create and configure a Resource Execution (RE) agent"""
        # Assuming REAgentOptions exists and is similar to others
        return REAgent(REAgentOptions(
            name="RE_Agent",
            description=(
                "Resource Execution Agent specialized in executing specific tasks or workflows. "
                f"You are control {numberagent} instance RE in this swarm."
                # Add more specific description based on REAgent's capabilities
            ),
            api_key=self.api_key,
            model=self.openai_model,
            project_auth_token=self.project_auth_token,
            project_id=self.project_id,
            api_base_url=self.rivalz_url,
            inference_config={
                'maxTokens': 500,
                'temperature': 0.5,
            },
            callbacks=self.callbacks,
            streaming = False,
        ))

    async def _create_rx_agent(self):
        """Create and configure an RX Rivalz agent for social media"""
        try:
            Logger.info("Creating RX agent...")
            custom_classifier = create_classifier()
            default_agent = create_default_agent()
            
            # Await the rx_supervisor creation
            rx_supervisor = await create_rx_supervisor(
                storage=self.shared_storage,
                project_id=self.project_id
            )
            
            orchestrator = SwarmOrchestrator(
                options=OrchestratorConfig(
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
                storage=self.shared_storage,
            )
            
            # Add the supervisor to the orchestrator
            orchestrator.add_agent(rx_supervisor)
            Logger.info(f"Created orchestrator with project_id: {self.project_id}")
            return orchestrator
            
        except Exception as e:
            Logger.error(f"Error creating RX agent: {str(e)}")
            raise
    
    
    def _get_agent_by_type(self, agent_type: str) -> Optional[Agent]:
        """Get agent instance by type"""
        agent_type = agent_type.lower()
        if agent_type == "rc":
            return self.rc_agent
        elif agent_type == "rd":
            return self.rd_agent
        elif agent_type == "re": # Added REAgent
            return self.re_agent
        elif agent_type == "rx":
            return self.rx_agent
        return None
    
    def generate_start_message(self) -> str:
        """Generate initial message showing available team resources."""
        if not self.team_info:
            return "Team information not available. Please try again later."
        
        message = "You are interacting with the following team resources:\n"
        
        # Add resource counts
        resource_names = {
            'rx': 'RX (Social Media) Agents',
            'rc': 'RC (Compute) Agents',
            'rd': 'RD (Data) Agents',
            're': 'RE (Execution) Agents'
        }
        
        for resource_key, display_name in resource_names.items():
            count = self.team_info.get(resource_key, 0)
            if count > 0:
                message += f"- {display_name}: {count}\n"
        
        # Add swarm information if available
        info = self.team_info.get('info', {})
        if info:
            swarm_level = info.get('swarm_level', 'Unknown')
            message += f"\nSwarm Level: {swarm_level}\n"
            
            # Add any additional team info that might be useful
            total_resources = self.team_info.get('total_resources', 0)
            if total_resources:
                message += f"Total Resources: {total_resources}\n"
                
        # Add last updated timestamp
        last_updated = self.team_info.get('last_updated')
        if last_updated:
            message += f"\nLast Updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return message
    

    async def process_request(self, input_text:str,
        user_id:str,
        session_id:str,
        chat_history:list=[],
        additional_params:dict= {},
        agent_type:str='rx') -> str:
        """Process a message using the specified agent type"""
         
        """Get agent instance by type"""
        agent_type = agent_type.lower()
        if agent_type == "rc":
            response: ConversationMessage = await self.rc_agent.process_request(input_text= input_text, user_id=user_id, session_id=session_id, chat_history=chat_history, additional_params=additional_params)
            metadata = self.create_metadata(self.rc_agent, input_text, user_id, session_id, additional_params)
            return AgentResponse(metadata, response, self.rc_agent.is_streaming_enabled())
        elif agent_type == "rd":
            response: ConversationMessage = await self.rd_agent.process_request(input_text= input_text, user_id=user_id, session_id=session_id, chat_history=chat_history, additional_params=additional_params)
            metadata = self.create_metadata(self.rd_agent, input_text, user_id, session_id, additional_params)
            return AgentResponse(metadata, response, self.rd_agent.is_streaming_enabled())
        elif agent_type == "re": # Added REAgent
            response: ConversationMessage = await self.re_agent.process_request(input_text= input_text, user_id=user_id, session_id=session_id, chat_history=chat_history, additional_params=additional_params)
            metadata = self.create_metadata(self.re_agent, input_text, user_id, session_id, additional_params)
            return AgentResponse(metadata, response, self.re_agent.is_streaming_enabled())
        elif agent_type == "rx":
            response: AgentResponse = await self.rx_agent.route_request(user_input= input_text, user_id=user_id, session_id=session_id, chat_history=chat_history, additional_params=additional_params)
            return response
        return None
    
    
    def create_metadata(self,
                        selected_agent: Agent,
                        user_input: str,
                        user_id: str,
                        session_id: str,
                        additional_params: Dict[str, str]) -> AgentProcessingResult:
        base_metadata = AgentProcessingResult(
            user_input=user_input,
            agent_id="no_agent_selected",
            agent_name="No Agent",
            user_id=user_id,
            session_id=session_id,
            additional_params=additional_params
        )
 
        base_metadata.agent_id = selected_agent.id
        base_metadata.agent_name = selected_agent.name

        return base_metadata

