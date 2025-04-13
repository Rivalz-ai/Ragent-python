import requests
import json
from typing import List, Optional
from dataclasses import dataclass, field
from rAgent.agents import SupervisorAgent, SupervisorAgentOptions
from rAgent.types import ConversationMessage, ParticipantRole
from rAgent.utils import Logger
from .RXRivalzAgent import RXRivalzAgent, RXAgentRivalzOptions
from rAgent.ragents.x_tool import Xtools
from datetime import datetime, timedelta
import threading
import asyncio
import httpx
@dataclass
class RXTeamSupervisorRivalzOptions(SupervisorAgentOptions):
    authen_key: str =field(default="")
    project_id: str = field(default="")
    api_url: str = "https://staging-rome-api-v2.rivalz.ai"
    token_refresh_minutes: int = 110
    number_of_agents: int = 3
    

class RXTeamSupervisorRivalz(SupervisorAgent):
    def __init__(self, options: RXTeamSupervisorRivalzOptions):
        self.authen_key = options.authen_key
        self.project_id = options.project_id
        self.api_url = options.api_url
        self.token_refresh_minutes = options.token_refresh_minutes
        self.last_refresh_time = None
        self.refresh_timer = None
        self.number_of_agents = options.number_of_agents or 3
        self.team = []
        self.x_ids = []
        super().__init__(options)

    def authenticate_and_create_team(self) -> None:
        """Fetch access tokens and create RX agent team"""
        try:
            params = {'authen_key': self.authen_key, 'project_id': self.project_id}
            api_url = f"{self.api_url}/agent/swarm"
            Logger.info(f"Authenticating with RX API at {api_url} with params: {params}")
            try:
                with httpx.Client(timeout=20) as client:
                    response = client.get(api_url, params=params)
            except httpx.RequestError as exc:
                Logger.error(f"An error occurred while requesting {exc.request.url!r}: {exc}")
                raise Exception("Request error")
            if response.status_code == 200:
                data = response.json()
                self._create_rx_team(data)

                self.last_refresh_time = datetime.now()
                self._schedule_token_refresh()
            else:
                Logger.warn(f"Not Authentication! team is None")
                self.team = []
        except Exception as e:
            Logger.error(f"Authentication error: {str(e)}")
            raise Exception("Authentication error")

    def _create_rx_team(self, auth_data: dict) -> None:
        """Create RX agents team from authentication data"""
        try:
            rx_agents = []
            # Access the nested 'data' array
            auth_data = auth_data.get('data', {})
            if not auth_data:
                raise ValueError("No data found in authentication response")
            resources = auth_data.get('resources', {})
            if not resources:
                raise ValueError("No resources found in authentication data")
            token_list = resources.get('rx', [])
            if not token_list:
                raise ValueError("No rx agent found in authentication data")
            
            num_agents = min(self.number_of_agents, len(token_list))
            self.number_of_agents = len(token_list)
            Logger.info(f"Creating RX team with {num_agents} agents")
            self.x_ids = []
            self.team_info = {"type":"RX", "num_agents": len(token_list)}
            Logger.info(f"Successfully created RX team with {self.number_of_agents} agents")
            # for idx, token_data in enumerate(token_list):
            #     # Extract tokens and expiration
            #     # if idx >= num_agents:
            #     #     break
            #     self.x_ids.append(token_data.get('x_id'))
            #     access_token = token_data.get('access_token')
            #     refresh_token = token_data.get('refresh_token')
            #     followers_count = token_data.get('followers_count')
            #     following_count = token_data.get('following_count')
            #     tweet_count = token_data.get('tweet_count')
            #     like_count = token_data.get('like_count')
            #     example_post = token_data.get('example_post')
            #     style_description = token_data.get('style_description')
            #     x_id = token_data.get('x_id')
            #     project_auth_token = self.authen_key
            #     api_post = self.api_url
            #     if not x_id or x_id =="":
            #         Logger.warn(f"Skipping agent {idx + 1} due to missing x_id")
            #         continue

            #     agent = RXRivalzAgent(RXAgentRivalzOptions(
            #         name=f"RX_Agent_{x_id}",
            #         api_key=self.lead_agent.api_key,  # Use same OpenAI key as lead agent
            #         model=self.lead_agent.model,  # Use same OpenAI model as lead agent
            #         base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
            #         xaccesstoken=access_token,
            #         xrefreshtoken=refresh_token,
            #         x_id=x_id,
            #         followers_count=followers_count,
            #         following_count=following_count,
            #         tweet_count=tweet_count,
            #         like_count=like_count,
            #         example_post=example_post,
            #         style_description=style_description,
            #         project_auth_token=project_auth_token,
            #         api_post=api_post, 
            #         project_id=self.project_id,
            #         inference_config={
            #             'maxTokens': 500,
            #             'temperature': 0.5,
            #             'topP': 0.8,
            #             'stopSequences': []
            #         },
            #         callbacks=self.callbacks,
            #         share_global_memory=True,
            #     ))
            #     rx_agents.append(agent)
            #     Logger.info(f"Created RX_Agent_{idx + 1} with access token")
            
            # if not rx_agents:
            #     raise ValueError("Failed to create any RX agents from authentication data")

            # self.team = rx_agents
            # Logger.info(f"Successfully created RX team with {len(rx_agents)} agents")
        
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
            self.authenticate_and_create_team()      
            # Schedule next refresh
            self._schedule_token_refresh()
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

    async def select_agent(self, num_agents:int, content: str) -> str:
        """Send messages to a random selection of agents."""
        Logger.info("Doing the true select agent")
        try:
            tasks = []
            url = self.api_url +"/agent/rx"
            params = {
                'authen_key': self.authen_key,
                'num': num_agents,
                'project_id': self.project_id
            }
            response = requests.get(url, params=params)
            tempt_team = []
            if response.status_code == 200:
                data = response.json()
                tempt_team = self.select_temp_team(data)
            for agent in tempt_team:
                tasks.append(
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.send_message,
                            agent,
                            content,
                            self.user_id,
                            self.session_id,
                            self.additional_params
                        )
                    )
                )

            if not tasks:
                return ''

            responses = await asyncio.gather(*tasks)
            return ''.join(responses)

        except Exception as e:
            Logger.error(f"Error in random_messages: {e}")
            raise e
    
    def select_temp_team(self, auth_data: dict) -> None:
        """Create RX agents team from authentication data"""
        try:
            rx_agents = []
            # Access the nested 'data' array
            token_list = auth_data.get('data', [])
            if not token_list:
                raise ValueError("No rx agent found in authentication data")
            
            for idx, token_data in enumerate(token_list):
                # Extract tokens and expiration
                # if idx >= num_agents:
                #     break
                self.x_ids.append(token_data.get('x_id'))
                access_token = token_data.get('access_token')
                refresh_token = token_data.get('refresh_token')
                followers_count = token_data.get('followers_count')
                following_count = token_data.get('following_count')
                tweet_count = token_data.get('tweet_count')
                like_count = token_data.get('like_count')
                example_post = token_data.get('example_post')
                style_description = token_data.get('style_description')
                x_id = token_data.get('x_id')
                project_auth_token = self.authen_key
                api_post = self.api_url
                if not x_id or x_id =="":
                    Logger.warn(f"Skipping agent {idx + 1} due to missing x_id")
                    continue

                agent = RXRivalzAgent(RXAgentRivalzOptions(
                    name=f"RX_Agent_{x_id}",
                    api_key=self.lead_agent.api_key,  # Use same OpenAI key as lead agent
                    model=self.lead_agent.model,  # Use same OpenAI model as lead agent
                    base_url=self.lead_agent.base_url,  # Use same OpenAI base URL as lead agent
                    xaccesstoken=access_token,
                    xrefreshtoken=refresh_token,
                    x_id=x_id,
                    followers_count=followers_count,
                    following_count=following_count,
                    tweet_count=tweet_count,
                    like_count=like_count,
                    example_post=example_post,
                    style_description=style_description,
                    project_auth_token=project_auth_token,
                    api_post=api_post, 
                    project_id=self.project_id,
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
            Logger.info(f"Successfully created RX team with {len(rx_agents)} agents")
            return rx_agents
        
        except Exception as e:
            Logger.error(f"Error creating RX tempt team: {str(e)}")
            raise