import requests
import json
from typing import List, Optional
from dataclasses import dataclass, field
from supervisor_agent1 import SupervisorAgent, SupervisorAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from multi_agent_orchestrator.utils import Logger
from RXAgent import RXAgent, RXAgentOptions
from tweeter_tool import Xtools
from datetime import datetime, timedelta
import threading
@dataclass
class RXTeamSupervisorOptions(SupervisorAgentOptions):
    authen_key: str =field(default="")
    api_url: str = " https://rome-api-v2.rivalz.ai/agent"
    token_refresh_minutes: int = 110

class RXTeamSupervisor(SupervisorAgent):
    def __init__(self, options: RXTeamSupervisorOptions):
        self.authen_key = options.authen_key
        self.api_url = options.api_url
        self.token_refresh_minutes = options.token_refresh_minutes
        self.last_refresh_time = None
        self.refresh_timer = None
        super().__init__(options)

    def authenticate_and_create_team(self) -> None:
        """Fetch access tokens and create RX agent team"""
        try:
            params = {'authen_key': self.authen_key}
            response = requests.get(self.api_url, params=params)
            if response.status_code == 200:
                data = response.json()
                self._create_rx_team(data)

                self.last_refresh_time = datetime.now()
                self._schedule_token_refresh()
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
    def _schedule_token_refresh(self, delay_minutes=None) -> None:
        """Schedule the next token refresh"""
        # Cancel any existing timer
        if self.refresh_timer:
            self.refresh_timer.cancel()
        
        # Calculate time until next refresh
        if delay_minutes is None:
            delay_minutes = self.token_refresh_minutes
            
        # Convert minutes to seconds for the timer
        delay_seconds = delay_minutes * 60
        
        Logger.info(f"Scheduling next token refresh in {delay_minutes} minutes")
        
        # Create and start the timer
        self.refresh_timer = threading.Timer(delay_seconds, self.refresh_tokens)
        self.refresh_timer.daemon = True  # Allow program to exit if only the timer is running
        self.refresh_timer.start()

    def initialize(self) -> None:
        """Initialize the supervisor with authenticated team"""
        self.authenticate_and_create_team()

    def refresh_tokens(self) -> None:
        """Refresh tokens for existing agents"""
        Logger.info("Refreshing access tokens...")
        try:
            params = {'authen_key': self.authen_key}
            response = requests.get(self.api_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                token_list = data.get('data', [])
                
                if not token_list:
                    raise ValueError("No access tokens found in refresh response")

                access_tokens = []
                # Update tokens for existing agents
                for idx, token_data in enumerate(token_list):
                    if idx >= len(self.team):
                        break  # Don't process more tokens than we have agents
                        
                    access_token = token_data.get('access_token')
                    if access_token:
                        access_tokens.append(access_token)
                        # Call the update_access_token method
                if len(access_tokens) <= len(self.team):
                    for idx, agent in enumerate(self.team):
                        if idx < len(access_tokens):
                            agent.update_access_token(access_tokens[idx])
                        else:
                            Logger.warn(f"No access token found for RX_Agent_{idx + 1} during refresh")
                    self.team = self.team[:len(access_tokens)]
                else:
                    for idx, agent in enumerate(self.team):
                        if idx < len(access_tokens):
                            agent.update_access_token(access_tokens[idx])
                        else:
                            break
                    Logger.warn("More access tokens found than existing agents")
                    # adding new agents
                    for idx in range(len(self.team), len(access_tokens)):
                        agent = RXAgent(RXAgentOptions(
                            name=f"RX_Agent_{idx + 1}",
                            description=(
                                f"Social media (Twitter/X) posting agent #{idx + 1}"
                                " - can post tweets and handle replies."
                            ),
                            api_key=self.lead_agent.api_key,  # Use same OpenAI key as lead agent
                            model=self.lead_agent.model,  # Use same OpenAI model as lead agent
                            base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
                            xaccesstoken=access_tokens[idx],
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
                        self.team.append(agent)
                        Logger.info(f"Created RX_Agent_{idx + 1} with access token")

                Logger.info(f"Successfully refreshed tokens for {min(len(token_list), len(self.team))} agents")
                
                # Schedule next refresh
                self._schedule_token_refresh()
            else:
                Logger.error(f"Token refresh failed with status {response.status_code}")
                # Try again after a short delay
                self._schedule_token_refresh(delay_minutes=5)
                
        except Exception as e:
            Logger.error(f"Error refreshing tokens: {str(e)}")
            # Try again after a short delay
            self._schedule_token_refresh(delay_minutes=5)
    def __del__(self):
        """Clean up timers when object is destroyed"""
        if self.refresh_timer:
            self.refresh_timer.cancel()
    
    def force_token_refresh(self) -> None:
        """
        Force an immediate refresh of access tokens.
        This is useful for refreshing tokens when a new user session starts.
        """
        Logger.info("Forcing immediate token refresh on session start")
        # Cancel any existing timer
        if self.refresh_timer:
            self.refresh_timer.cancel()
            self.refresh_timer = None
        
        # Immediately refresh tokens
        self.refresh_tokens()