import sys
import os
# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./..")))

import os
from dotenv import load_dotenv
from rAgent.orchestrator import SwarmOrchestrator, OrchestratorConfig
from rAgent.storage import InMemoryChatStorage 
from backend.agents import create_health_agent, create_travel_agent,create_rx_team, create_default_agent,create_classifier
import re

from rAgent.agents import SupervisorAgent
from rAgent.utils import Logger
# Load environment variables from .env file
load_dotenv()
Logger.info("Environment variables loaded")
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")


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
rx_supervisor = create_rx_team(storage = shared_storage, num_agents=3)
Logger.info("All agents created successfully")

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
    storage=shared_storage,
)

# Add all agents
orchestrator.add_agent(rx_supervisor)
orchestrator.add_agent(health_agent)
orchestrator.add_agent(travel_agent)
Logger.info("Agents added to orchestrator")

