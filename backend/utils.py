from rAgent.orchestrator import SwarmOrchestrator
from rAgent.agents import SupervisorAgent
import re
import yaml
def generate_start_message(orchestrator: SwarmOrchestrator) -> str:
    message = "You are interacting with the following agents:\n"
    for agent_id in orchestrator.agents:
        agent = orchestrator.agents[agent_id]
        if isinstance(agent, SupervisorAgent):
            agent_counts = {}
            for team_agent in agent.team:
                agent_type = type(team_agent).__name__
                if agent_type in agent_counts:
                    agent_counts[agent_type] += 1
                else:
                    agent_counts[agent_type] = 1
            agent_details = "\n".join([f"{agent_type} - Count: {count}" for agent_type, count in agent_counts.items()])
            message += f"- {agent.name} (SupervisorAgent) with the following team:\n{agent_details}\n"
        else:
            message += f"- {agent.name} ({type(agent).__name__})\n"
    return message


def clean_text(extracted_text: str) -> str:
    """Clean the extracted text by removing tags and ensuring only one instance of [AgentName]."""
    # Remove all occurrences of <\startagent> and <\endagent>
    cleaned_text = re.sub(r'<\\startagent>|<\\endagent>', '', extracted_text)
    # Ensure only one instance of [AgentName]
    agent_name_match = re.search(r'\[([^\]]+)\]', cleaned_text)
    if agent_name_match:
        agent_name = agent_name_match.group(0)
        cleaned_text = re.sub(r'\[([^\]]+)\]', '', cleaned_text)
        cleaned_text = agent_name + " " + cleaned_text
    return cleaned_text.strip()


def read_x_token_yml(file_path: str = "x_token.yml") -> list:
    """
    Read the x_token.yml file and return its contents as a list of dictionaries.
    
    Args:
        file_path (str): Path to the x_token.yml file. Defaults to "x_token.yml".
        
    Returns:
        list: List of dictionaries containing the parsed YAML data.
    """
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
            if not isinstance(data, dict):
                return data if data else {}
            return data
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return {}