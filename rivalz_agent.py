import os
import uuid
from typing import Dict, Optional, Union, List, Any
import logging
import asyncio
import aiohttp
from dotenv import load_dotenv

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


class RivalzAgent:
    """
    Unified agent class that manages different Rivalz agent types (RC, RD, RE, RX)
    and provides a consistent interface for interaction with these agents.
    """
    
    def __init__(self, project_id: str, shared_storage: InMemoryChatStorage,callbacks: AgentCallbacks = None):
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
        self.callbacks =callbacks
        self.shared_storage = shared_storage
        # Initialize storage
        self._fetch_resource_info()
            # Default to initializing all types if none specified
        self._initialize_agent()

    def _fetch_resource_info(self):
        """
        Fetch available agent types from the API and initialize them.
        """
        try:
            params = {'authen_key': self.project_auth_token, 'project_id': self.project_id}
            api_url = f"{self.rivalz_url}/agent/swarm"
            Logger.info(f"Fetching team info from API at {api_url}")
            
            with httpx.AsyncClient(timeout=20) as client:
                response = client.get(api_url, params=params)
                
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
            Logger.error(f"Error fetching team info: {str(e)}")
            self.team_info = {}    
    
    def _initialize_agent(self):
        """
        Initialize agent types based on available resources in team_info.
        """
        
        if not self.team_info:
            Logger.error("Team info not available. Cannot initialize agents.")
            raise ValueError("Team info not available. Cannot initialize agents.")
        
        self.polling_tasks = {}
        self.polling_active = False
        
        # Define agent types with their creation methods and resource keys
        agent_configs = {
            'rc': {'attr': 'rc_agent', 'creator': self._create_rc_agent, 'name': 'RC'},
            'rd': {'attr': 'rd_agent', 'creator': self._create_rd_agent, 'name': 'RD'},
            're': {'attr': 're_agent', 'creator': self._create_re_agent, 'name': 'RE'},
            'rx': {'attr': 'rx_agent', 'creator': self._create_rx_agent, 'name': 'RX'}
        }

        # Initialize each agent type based on available resources
        for agent_type, config in agent_configs.items():
            try:
                if self.team_info.get(agent_type, 0) > 0:
                    # Pass numberagent parameter for RC, RD, RE agents
                    if agent_type in ['rc', 'rd', 're']:
                        numberagent = self.team_info.get(agent_type, 0)
                        setattr(self, config['attr'], config['creator'](numberagent))
                    else:
                        # RX agent doesn't need numberagent parameter
                        setattr(self, config['attr'], config['creator']())
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
        ))

    async def _create_rx_agent(self) -> RXRivalzAgent:
        """Create and configure an RX Rivalz agent for social media"""
        # For RX agent, check if we have token info from environment
        Logger.info("Shared storage initialized")
        Logger.info("Creating agents...")
        custom_classifier = create_classifier()
        default_agent = create_default_agent()
        # Add await keyword to call the async function properly
        rx_supervisor =  asyncio.run(create_rx_supervisor(storage = self.shared_storage, project_id=self.project_id))
        # Initialize orchestrator
        Logger.info("Initializing orchestrator")
        orchestrator = SwarmOrchestrator(options=OrchestratorConfig(
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
        orchestrator.add_agent(rx_supervisor)
        Logger.info(f"Creating orchestrator with project_id: {self.project_id}")
        return orchestrator
    
    
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
    
    