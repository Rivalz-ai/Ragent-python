import requests
import json
from typing import List, Optional, Dict, Any, Type, Callable, Awaitable, Union, Set
from dataclasses import dataclass, field
from rAgent.agents import SupervisorAgent, SupervisorAgentOptions
from rAgent.types import ConversationMessage, ParticipantRole
from rAgent.utils import Logger
from .RXRivalzAgent import RXRivalzAgent, RXAgentRivalzOptions, SocialMediaClient
from rAgent.ragents.x_tool import Xtools
from datetime import datetime, timedelta
import threading
import asyncio
import httpx
from abc import ABC, abstractmethod
import random

# Base class for team authentication strategies
class AuthenticationStrategy(ABC):
    """
    Abstract base class for authentication strategies.
    Supports different ways to authenticate and obtain agent credentials.
    """
    @abstractmethod
    async def authenticate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate and retrieve token data
        
        Args:
            config: Configuration parameters for authentication
            
        Returns:
            Dict containing authentication data
        """
        pass
    
    @abstractmethod
    def extract_agent_data(self, auth_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract agent data from authentication response
        
        Args:
            auth_data: Authentication data from authenticate method
            
        Returns:
            List of dictionaries with agent configuration data
        """
        pass

# Concrete implementation for Rivalz API authentication
class RivalzAPIAuthStrategy(AuthenticationStrategy):
    """Authentication strategy for Rivalz API"""
    
    async def authenticate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Rivalz API and get token data"""
        authen_key = config.get('authen_key')
        project_id = config.get('project_id')
        api_url = config.get('api_url', "https://staging-rome-api-v2.rivalz.ai")
        
        if not authen_key or not project_id:
            raise ValueError("Authentication key and project ID are required")
            
        params = {'authen_key': authen_key, 'project_id': project_id}
        api_endpoint = f"{api_url}/agent/swarm"
        
        Logger.info(f"Authenticating with Rivalz API at {api_endpoint}")
        
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(api_endpoint, params=params)
                
            if response.status_code != 200:
                Logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                return {}
                
            data = response.json()
            Logger.info("Authentication successful")
            return data
            
        except httpx.RequestError as exc:
            Logger.error(f"Request error during authentication: {str(exc)}")
            raise
    
    def extract_agent_data(self, auth_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract agent data from Rivalz API response"""
        try:
            data = auth_data.get('data', {})
            if not data:
                Logger.error("No data found in authentication response")
                return []
                
            resources = data.get('resources', {})
            if not resources:
                Logger.error("No resources found in authentication data")
                return []
                
            token_list = resources.get('rx', [])
            if not token_list:
                Logger.error("No rx agent found in authentication data")
                return []
                
            return token_list
            
        except Exception as e:
            Logger.error(f"Error extracting agent data: {str(e)}")
            return []

# Concrete implementation for API RX endpoint
class RivalzRXEndpointStrategy(AuthenticationStrategy):
    """Authentication strategy for Rivalz RX endpoint"""
    
    async def authenticate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Authenticate with Rivalz RX endpoint and get token data"""
        authen_key = config.get('authen_key')
        project_id = config.get('project_id')
        api_url = config.get('api_url', "https://staging-rome-api-v2.rivalz.ai")
        num_agents = config.get('num', 3)
        
        if not authen_key or not project_id:
            raise ValueError("Authentication key and project ID are required")
            
        params = {
            'authen_key': authen_key,
            'num': num_agents,
            'project_id': project_id
        }
        api_endpoint = f"{api_url}/agent/rx"
        
        Logger.info(f"Fetching agents from RX endpoint at {api_endpoint}")
        
        try:
            # Using synchronous request as original code
            response = requests.get(api_endpoint, params=params)
            
            if response.status_code != 200:
                Logger.error(f"RX endpoint request failed: {response.status_code} - {response.text}")
                return {}
                
            data = response.json()
            Logger.info(f"Successfully retrieved data for {len(data.get('data', []))} agents")
            return data
            
        except Exception as exc:
            Logger.error(f"Error fetching from RX endpoint: {str(exc)}")
            raise
    
    def extract_agent_data(self, auth_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract agent data from RX endpoint response"""
        try:
            token_list = auth_data.get('data', [])
            if not token_list:
                Logger.error("No data found in RX endpoint response")
                return []
                
            return token_list
            
        except Exception as e:
            Logger.error(f"Error extracting agent data from RX endpoint: {str(e)}")
            return []

# Factory for creating agents
class AgentFactory:
    """Factory for creating RXRivalzAgent instances"""
    
    @staticmethod
    def create_agent(agent_config: Dict[str, Any], base_config: Dict[str, Any]) -> RXRivalzAgent:
        """
        Create an RXRivalzAgent with the provided configuration
        
        Args:
            agent_config: Agent-specific configuration (tokens, profile data)
            base_config: Base configuration (API keys, inference settings)
            
        Returns:
            RXRivalzAgent instance
        """
        try:
            # Extract needed information from configs
            x_id = agent_config.get('x_id')
            if not x_id:
                raise ValueError("Missing x_id in agent configuration")
                
            # Required agent configuration
            options = RXAgentRivalzOptions(
                name=f"RX_Agent_{x_id}",
                api_key=base_config.get('api_key'),
                model=base_config.get('model', 'gpt-4o'),
                base_url=base_config.get('base_url'),
                
                # X API configuration
                xaccesstoken=agent_config.get('access_token'),
                xrefreshtoken=agent_config.get('refresh_token'),
                x_id=x_id,
                
                # Rivalz configuration
                project_auth_token=base_config.get('project_auth_token'),
                project_id=base_config.get('project_id'),
                api_post=base_config.get('api_url'), 
                
                # Account metadata
                followers_count=agent_config.get('followers_count'),
                following_count=agent_config.get('following_count'),
                tweet_count=agent_config.get('tweet_count'),
                like_count=agent_config.get('like_count'),
                example_post=agent_config.get('example_post'),
                style_description=agent_config.get('style_description'),
                
                # Inference configuration
                inference_config=base_config.get('inference_config', {
                    'maxTokens': 500,
                    'temperature': 0.5,
                    'topP': 0.8,
                    'stopSequences': []
                }),
                
                # Additional settings
                callbacks=base_config.get('callbacks'),
                share_global_memory=base_config.get('share_global_memory', True),
                streaming=base_config.get('streaming', False),
                
                # Support for custom prompts
                prompt_templates=base_config.get('prompt_templates', {}),
                content_formatting=base_config.get('content_formatting', {})
            )
            
            # Create and return the agent
            agent = RXRivalzAgent(options)
            
            # Add session ID if available
            if 'session_id' in base_config:
                agent.set_session_id(base_config['session_id'])
                
            Logger.info(f"Created agent RX_Agent_{x_id}")
            return agent
            
        except Exception as e:
            Logger.error(f"Error creating agent: {str(e)}")
            raise

# Class for agent team management
class AgentTeamManager:
    """Manages a team of agents with token refresh capabilities"""
    
    def __init__(self, refresh_callback: Callable[[], None], refresh_interval_minutes: int = 110):
        """
        Initialize the team manager
        
        Args:
            refresh_callback: Function to call when token refresh is needed
            refresh_interval_minutes: Interval in minutes between token refreshes
        """
        self.team: List[RXRivalzAgent] = []
        self.x_ids: Set[str] = set()
        self.refresh_callback = refresh_callback
        self.refresh_interval_minutes = refresh_interval_minutes
        self.refresh_timer = None
        self.last_refresh_time = None
    
    def set_team(self, agents: List[RXRivalzAgent]) -> None:
        """Set the current team of agents"""
        self.team = agents
        self.x_ids = {agent.x_id for agent in agents if agent.x_id}
        Logger.info(f"Team updated with {len(agents)} agents")
    
    def schedule_refresh(self, delay_minutes: Optional[int] = None) -> None:
        """Schedule the next token refresh"""
        # Cancel any existing timer
        if self.refresh_timer:
            self.refresh_timer.cancel()
            self.refresh_timer = None
        
        # Use default interval if not specified
        if delay_minutes is None:
            delay_minutes = self.refresh_interval_minutes
        
        # Convert to seconds
        delay_seconds = delay_minutes * 60
        
        Logger.info(f"Scheduling next token refresh in {delay_minutes} minutes")
        
        # Create and start timer
        self.refresh_timer = threading.Timer(delay_seconds, self.refresh_callback)
        self.refresh_timer.daemon = True
        self.refresh_timer.start()
        
    def force_refresh(self) -> None:
        """Force an immediate refresh of tokens"""
        Logger.info("Forcing immediate token refresh")
        
        # Cancel existing timer
        if self.refresh_timer:
            self.refresh_timer.cancel()
            self.refresh_timer = None
        
        # Perform refresh
        self.refresh_callback()
    
    def cleanup(self) -> None:
        """Clean up resources"""
        if self.refresh_timer:
            self.refresh_timer.cancel()
            self.refresh_timer = None
        
        self.team = []
        self.x_ids = set()

@dataclass
class RXTeamSupervisorRivalzOptions(SupervisorAgentOptions):
    authen_key: str = field(default="")
    project_id: str = field(default="")
    api_url: str = "https://staging-rome-api-v2.rivalz.ai"
    token_refresh_minutes: int = 110
    number_of_agents: int = 3
    # New options for enhanced agent configuration
    agent_specialization: Optional[str] = None
    enhanced_content_generation: bool = False
    custom_prompt_templates: Dict[str, str] = field(default_factory=dict)
    content_formatting: Dict[str, Any] = field(default_factory=dict)

class RXTeamSupervisorRivalz(SupervisorAgent):
    """
    Supervisor for a team of RXRivalzAgent instances.
    Handles authentication, team creation, and token refresh.
    """
    
    def __init__(self, options: RXTeamSupervisorRivalzOptions):
        """Initialize the supervisor with the provided options"""
        # Initialize base attributes from options
        self.authen_key = options.authen_key
        self.project_id = options.project_id
        self.api_url = options.api_url
        self.token_refresh_minutes = options.token_refresh_minutes
        self.number_of_agents = options.number_of_agents or 3
        
        # Enhanced options
        self.agent_specialization = options.agent_specialization
        self.enhanced_content_generation = options.enhanced_content_generation
        self.custom_prompt_templates = options.custom_prompt_templates
        self.content_formatting = options.content_formatting
        
        # Initialize team manager
        self.team_manager = AgentTeamManager(
            refresh_callback=self.refresh_tokens,
            refresh_interval_minutes=self.token_refresh_minutes
        )
        
        # Authentication strategies
        self.auth_strategies = {
            'swarm': RivalzAPIAuthStrategy(),
            'rx': RivalzRXEndpointStrategy()
        }
        
        # Set default authentication strategy
        self.current_auth_strategy = 'swarm'
        
        # Initialize empty team and x_ids for compatibility
        self.team = []
        self.x_ids = []
        
        # Call parent constructor
        super().__init__(options)

    async def authenticate_and_create_team(self) -> None:
        """Fetch access tokens and create RX agent team"""
        try:
            Logger.info(f"Starting authentication with strategy: {self.current_auth_strategy}")
            
            # Get the right authentication strategy
            auth_strategy = self.auth_strategies.get(self.current_auth_strategy)
            if not auth_strategy:
                raise ValueError(f"Unknown authentication strategy: {self.current_auth_strategy}")
            
            # Prepare configuration for authentication
            auth_config = {
                'authen_key': self.authen_key,
                'project_id': self.project_id,
                'api_url': self.api_url,
                'num': self.number_of_agents
            }
            
            # Authenticate and get token data
            auth_data = await auth_strategy.authenticate(auth_config)
            
            # Extract agent data
            agent_data_list = auth_strategy.extract_agent_data(auth_data)
            
            # Create agents
            await self._create_rx_team_from_data(agent_data_list)
            
            # Update timestamp and schedule refresh
            self.team_manager.last_refresh_time = datetime.now()
            self.team_manager.schedule_refresh()
            
            # Update references to team and x_ids for compatibility
            self.team = self.team_manager.team
            self.x_ids = list(self.team_manager.x_ids)
            
        except Exception as e:
            Logger.error(f"Authentication error: {str(e)}")
            # Empty the team on authentication failure
            self.team_manager.set_team([])
            self.team = []
            self.x_ids = []
            raise

    async def _create_rx_team_from_data(self, agent_data_list: List[Dict[str, Any]]) -> None:
        """Create RX agents from the provided data"""
        try:
            if not agent_data_list:
                raise ValueError("No agent data available to create team")
            
            # Limit to the requested number of agents
            num_agents = min(self.number_of_agents, len(agent_data_list))
            Logger.info(f"Creating RX team with up to {num_agents} agents")
            
            # Prepare base configuration
            base_config = {
                'api_key': self.lead_agent.api_key,
                'model': self.lead_agent.model,
                'base_url': self.lead_agent.base_url,
                'project_auth_token': self.authen_key,
                'project_id': self.project_id,
                'api_url': self.api_url,
                'callbacks': self.callbacks,
                'share_global_memory': True,
                'session_id': self.session_id if hasattr(self, 'session_id') else None,
                'prompt_templates': self.custom_prompt_templates,
                'content_formatting': self.content_formatting
            }
            
            # Create agents
            rx_agents = []
            for agent_data in agent_data_list[:num_agents]:
                # Skip agents without x_id
                x_id = agent_data.get('x_id')
                if not x_id:
                    Logger.warn(f"Skipping agent due to missing x_id")
                    continue
                
                try:
                    # Create agent
                    agent = AgentFactory.create_agent(agent_data, base_config)
                    
                    # Apply specialization if specified
                    if self.agent_specialization and self.agent_specialization in ["news", "marketing", "support"]:
                        # Create specialized version
                        specialized_options = RXAgentRivalzOptions(
                            api_key=agent.client.api_key,
                            project_auth_token=agent.project_auth_token,
                            project_id=agent.project_id,
                            x_id=agent.x_id,
                            model=agent.model,
                            base_url=agent.base_url,
                            xaccesstoken=agent.xaccesstoken,
                            xrefreshtoken=agent.xrefreshtoken,
                            style_description=agent.style_description,
                            prompt_templates=self.custom_prompt_templates,
                            content_formatting=self.content_formatting
                        )
                        
                        # Replace with specialized agent
                        agent = RXRivalzAgent.create_specialized(
                            self.agent_specialization, 
                            specialized_options
                        )
                        
                        # Set session ID if available
                        if hasattr(self, 'session_id'):
                            agent.set_session_id(self.session_id)
                    
                    rx_agents.append(agent)
                    
                except Exception as e:
                    Logger.error(f"Error creating agent for x_id {x_id}: {str(e)}")
                    # Continue with next agent
                    continue
            
            if not rx_agents:
                raise ValueError("Failed to create any RX agents from authentication data")
            
            # Update the team in manager
            self.team_manager.set_team(rx_agents)
            
            # Update references for compatibility
            self.team = rx_agents
            self.x_ids = [agent.x_id for agent in rx_agents if agent.x_id]
            
            Logger.info(f"Successfully created RX team with {len(rx_agents)} agents")
            
        except Exception as e:
            Logger.error(f"Error creating RX team: {str(e)}")
            raise

    def initialize(self) -> None:
        """Initialize the supervisor with authenticated team"""
        # Run asynchronously to work with async authentication method
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.authenticate_and_create_team())
        except Exception as e:
            Logger.error(f"Error initializing supervisor: {str(e)}")
            # Continue with empty team
            self.team = []
            self.x_ids = []

    def refresh_tokens(self) -> None:
        """Refresh tokens for existing agents"""
        Logger.info("Refreshing access tokens...")
        
        # Run authentication again to get fresh tokens
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.authenticate_and_create_team())
        except Exception as e:
            Logger.error(f"Error refreshing tokens: {str(e)}")
            # Schedule retry
            self.team_manager.schedule_refresh(delay_minutes=5)

    def __del__(self):
        """Clean up resources when object is destroyed"""
        self.team_manager.cleanup()

    def force_token_refresh(self) -> None:
        """Force an immediate refresh of access tokens"""
        self.team_manager.force_refresh()

    async def select_agent(self, num_agents: int, content: str) -> str:
        """Send messages to a selection of agents and get combined responses"""
        Logger.info(f"Selecting agents for content processing, requested: {num_agents}")
        
        try:
            # Use RX endpoint strategy to get fresh agents
            self.current_auth_strategy = 'rx'
            
            # Authenticate and get token data
            auth_strategy = self.auth_strategies.get(self.current_auth_strategy)
            auth_config = {
                'authen_key': self.authen_key, 
                'project_id': self.project_id,
                'api_url': self.api_url,
                'num': num_agents
            }
            
            auth_data = await auth_strategy.authenticate(auth_config)
            agent_data_list = auth_strategy.extract_agent_data(auth_data)
            
            if not agent_data_list:
                Logger.error("Failed to retrieve any agents for content processing")
                return ''
            
            # Prepare base configuration for agent creation
            base_config = {
                'api_key': self.lead_agent.api_key,
                'model': self.lead_agent.model,
                'base_url': self.lead_agent.base_url,
                'project_auth_token': self.authen_key,
                'project_id': self.project_id,
                'api_url': self.api_url,
                'callbacks': self.callbacks,
                'share_global_memory': True,
                'session_id': self.session_id if hasattr(self, 'session_id') else None,
                'prompt_templates': self.custom_prompt_templates,
                'content_formatting': self.content_formatting
            }
            
            # Create temporary agents for this request
            temp_agents = []
            for agent_data in agent_data_list:
                try:
                    agent = AgentFactory.create_agent(agent_data, base_config)
                    temp_agents.append(agent)
                except Exception as e:
                    Logger.error(f"Error creating temporary agent: {str(e)}")
                    # Continue with next agent
            
            if not temp_agents:
                Logger.error("Failed to create any temporary agents")
                return ''
            
            # Create tasks for processing content
            tasks = []
            for agent in temp_agents:
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
            
            # Wait for all tasks to complete
            responses = await asyncio.gather(*tasks)
            
            # Combine responses
            combined_response = ''.join(responses)
            return combined_response
            
        except Exception as e:
            Logger.error(f"Error selecting agents: {str(e)}")
            return ''

    # Enhanced methods to take advantage of new RXRivalzAgent capabilities
    
    async def get_optimized_content(self, content: str, theme: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate optimized content using the enhanced features
        
        Args:
            content: Original content
            theme: Optional content theme
            
        Returns:
            Dictionary with optimized content and analysis
        """
        if not self.team:
            Logger.error("No agents available for content optimization")
            return {'error': 'No agents available'}
        
        try:
            # Choose a random agent from the team
            agent = random.choice(self.team)
            
            # Optimize content
            optimized = agent.optimize_content_for_platform(content)
            
            result = {
                'original': content,
                'optimized': optimized
            }
            
            # Add engagement analysis if enhanced mode enabled
            if self.enhanced_content_generation:
                try:
                    analysis = agent.analyze_engagement_potential(optimized)
                    result['analysis'] = analysis
                    
                    # Add timing suggestion if theme provided
                    if theme:
                        timing = agent.suggest_optimal_posting_time(theme)
                        result['timing'] = timing
                except Exception as e:
                    Logger.error(f"Error during enhanced content analysis: {str(e)}")
            
            return result
            
        except Exception as e:
            Logger.error(f"Error optimizing content: {str(e)}")
            return {'error': str(e)}
    
    async def generate_variations(self, content: str, count: int = 3) -> List[str]:
        """
        Generate variations of content using the team
        
        Args:
            content: Original content
            count: Number of variations to generate
            
        Returns:
            List of content variations
        """
        if not self.team:
            Logger.error("No agents available for content variation")
            return []
        
        try:
            # Choose a random agent
            agent = random.choice(self.team)
            
            # Generate variations
            variations = await agent.generate_content_variations(content, count)
            return variations
            
        except Exception as e:
            Logger.error(f"Error generating content variations: {str(e)}")
            return []
    
    def set_specialization(self, specialization: Optional[str]) -> bool:
        """
        Set specialization for the team agents
        
        Args:
            specialization: Type of specialization (news, marketing, support, or None)
            
        Returns:
            True if successful, False otherwise
        """
        if specialization and specialization not in ["news", "marketing", "support"]:
            Logger.error(f"Invalid specialization: {specialization}")
            return False
        
        self.agent_specialization = specialization
        
        # Re-initialize team with new specialization
        try:
            self.initialize()
            return True
        except Exception as e:
            Logger.error(f"Error setting specialization: {str(e)}")
            return False