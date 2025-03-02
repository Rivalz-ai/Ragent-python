import requests
import json
from typing import List, Optional
from dataclasses import dataclass, field
from supervisor_agent1 import SupervisorAgent, SupervisorAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from multi_agent_orchestrator.utils import Logger
from RXAgent import RXAgent, RXAgentOptions
from tweeter_tool import Xtools
@dataclass
class RXTeamSupervisorOptions(SupervisorAgentOptions):
    authen_key: str =field(default="")
    api_url: str = " https://rome-api-v2.rivalz.ai/agent"

class RXTeamSupervisor(SupervisorAgent):
    def __init__(self, options: RXTeamSupervisorOptions):
        self.authen_key = options.authen_key
        self.api_url = options.api_url
        super().__init__(options)

    def authenticate_and_create_team(self) -> None:
        """Fetch access tokens and create RX agent team"""
        try:
            params = {'authen_key': self.authen_key}
            response = requests.get(self.api_url, params=params)
            if response.status_code == 200:
                data = response.json()
                self._create_rx_team(data)
            else:
                raise ValueError(f"Authentication failed with status {response.status_code}")
        except Exception as e:
            Logger.error(f"Authentication error: {str(e)}")
            raise

    def _create_rx_team(self, auth_data: dict) -> None:
        """Create RX agents team from authentication data"""
        try:
            rx_agents = []
            # Access the nested 'data' array
            token_list = auth_data.get('data', [])
            
            if not token_list:
                raise ValueError("No access tokens found in authentication data")

            for idx, token_data in enumerate(token_list):
                # Extract tokens and expiration
                access_token = token_data.get('access_token')

                if not access_token:
                    Logger.warn(f"Skipping agent {idx + 1} due to missing access token")
                    continue

                agent = RXAgent(RXAgentOptions(
                    name=f"RX_Agent_{idx + 1}",
                    description=(
                        f"Social media (Twitter/X) posting agent #{idx + 1}"
                        " - can post tweets and handle replies."
                    ),
                    api_key=self.lead_agent.api_key,  # Use same OpenAI key as lead agent
                    model=self.lead_agent.model,  # Use same OpenAI model as lead agent
                    base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
                    xaccesstoken=access_token,
                    inference_config={
                        'maxTokens': 500,
                        'temperature': 0.5,
                        'topP': 0.8,
                        'stopSequences': []
                    },  
                    tool_config={
                        'tool': Xtools,
                        'toolMaxRecursions': 5
                    },
                    callbacks=self.callbacks,
                    share_global_memory=True,
                ))
                rx_agents.append(agent)
                Logger.info(f"Created RX_Agent_{idx + 1} with access token")
            
            if not rx_agents:
                raise ValueError("Failed to create any RX agents from authentication data")

            self.team = rx_agents
            Logger.info(f"Successfully created RX team with {len(rx_agents)} agents")
        
        except Exception as e:
            Logger.error(f"Error creating RX team: {str(e)}")
            raise

    def initialize(self) -> None:
        """Initialize the supervisor with authenticated team"""
        self.authenticate_and_create_team()