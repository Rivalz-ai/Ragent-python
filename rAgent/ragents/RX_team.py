import requests
import json
from typing import List, Optional
from dataclasses import dataclass, field
from rAgent.agents import SupervisorAgent, SupervisorAgentOptions
from rAgent.utils import Logger
from rAgent.ragents.RXAgent import RXAgent
import threading
@dataclass
class RXTeamSupervisorOptions(SupervisorAgentOptions):
    token_refresh_minutes: int = 110
    number_of_agents: int = 3
    team: List[RXAgent] = field(default_factory=list)

class RXTeamSupervisor(SupervisorAgent):
    def __init__(self, options: RXTeamSupervisorOptions):
        self.token_refresh_minutes = options.token_refresh_minutes
        self.last_refresh_time = None
        self.refresh_timer = None
        self.number_of_agents = options.number_of_agents or 3
        self.team = options.team
        if len(self.team) == 0 or not all(isinstance(agent, RXAgent) for agent in self.team):
            raise ValueError("Invalid team provided")
        self._schedule_token_refresh()
        super().__init__(options)



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


    def refresh_tokens(self) -> None:
        """Refresh tokens for existing agents"""
        Logger.info("Refreshing access tokens...")
        try:
            removelist = []
            for ind, agent in enumerate(self.team):
                res = agent.refresh_access_token()
                if res == 200:
                    Logger.info(f"Agent {ind+1} token refreshed successfully")
                else:
                    Logger.error(f"Error refreshing token for agent {ind+1}")
                    removelist.append(ind)
            for ind in removelist:
                self.team.pop(ind)
            if len(self.team) < self.number_of_agents:
                Logger.warn(f"Number of agents in the team is less than expected. Expected: {self.number_of_agents}, Actual: {len(self.team)}")
                
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