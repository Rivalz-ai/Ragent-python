from rAgent.agents.agent import Agent, AgentOptions
from rAgent.types import ConversationMessage
from typing import Dict, List, Optional, Any, Union, AsyncIterable
import aiohttp
import json
import re
import os
from rAgent.utils import Logger
import time
import uuid

from typing import Dict, List, Union, AsyncIterable, Optional, Any
from dataclasses import dataclass, field
from openai import OpenAI
from rAgent.agents import Agent, AgentOptions
from rAgent.types import (
    ConversationMessage,
    ParticipantRole,
    OPENAI_MODEL_ID_GPT_O_MINI,
    TemplateVariables
)
import json
import requests
from rAgent.utils import Logger
from rAgent.retrievers import Retriever
from rAgent.utils import AgentTool, AgentTools
from rAgent.types import AgentProviderType

@dataclass
class RCAgentOptions(AgentOptions):
    """
    Options for configuring the RCAgent.
    """
    # OpenAI configuration
    api_key: str = None
    base_url: str = None
    model: Optional[str] = None
    streaming: Optional[bool] = None
    inference_config: Optional[Dict[str, Any]] = None
    
    # Agent configuration
    custom_system_prompt: Optional[Dict[str, Any]] = None
    retriever: Optional[Retriever] = None
    client: Optional[Any] = None
    extra_tools: Optional[Union[AgentTools, list[AgentTool]]] = None
    default_max_recursions: int = 2
    
    # RCAgent specific configuration
    project_auth_token: str = None
    project_id: str = None
    api_base_url: str = "https://staging-rome-api-v2.rivalz.ai/agent"
    
    # Additional configuration fields with default values
    prompt_templates: Dict[str, str] = field(default_factory=dict)


class RCAgent(Agent):
    """
    RCAgent is a specialized agent for interacting with compute resources.
    It can perform health checks and execute commands on the underlying system.
    """

    def __init__(self, options: RCAgentOptions):
        """
        Initialize the RCAgent with the provided options.
        """
        super().__init__(options)
        self._validate_options(options)
        
        # Initialize clients and configurations
        self._initialize_llm_client(options)
        self._initialize_agent_attributes(options)
        self._initialize_inference_config(options)
        self._initialize_tools(options.extra_tools)
        self._initialize_prompt_template(options)

    def _validate_options(self, options: RCAgentOptions) -> None:
        """
        Validate the required options for the agent.
        """
        if not options.api_key:
            raise ValueError("OpenAI API key is required")
        if not options.project_auth_token:
            raise ValueError("Project authentication token is required")

    def _initialize_llm_client(self, options: RCAgentOptions) -> None:
        """
        Initialize the OpenAI client based on the provided options.
        """
        self.client = options.client or OpenAI(api_key=options.api_key, base_url=options.base_url)

    def _initialize_agent_attributes(self, options: RCAgentOptions) -> None:
        """
        Initialize agent-specific attributes.
        """
        self.base_url = options.base_url
        self.model = options.model or OPENAI_MODEL_ID_GPT_O_MINI
        self.streaming = options.streaming or False
        self.retriever = options.retriever
        self.default_max_recursions = options.default_max_recursions
        self.session_id = ""
        
        # RCAgent specific attributes
        self.project_auth_token = options.project_auth_token
        self.api_base_url = options.api_base_url
        self.project_id = options.project_id

    def _initialize_inference_config(self, options: RCAgentOptions) -> None:
        """
        Initialize the inference configuration for the agent.
        """
        default_inference_config = {
            'maxTokens': 1000,
            'temperature': 0.2,
            'topP': None,
            'stopSequences': None
        }
        self.inference_config = {**default_inference_config, **(options.inference_config or {})}

    def _initialize_tools(self, extra_tools: Optional[Union[AgentTools, list[AgentTool]]]) -> None:
        """
        Configure tools for the agent.
        """
        get_health_tool = AgentTool(
            name="get_health",
            description="Get the health status of the RAgent system",
            properties={},
            func=self.get_health,
        )
        
        execute_command_tool = AgentTool(
            name="execute_command",
            description="Execute a command on the compute resource",
            properties={
                "command": {
                    "type": "string",
                    "description": "The command to execute on the system",
                },
            },
            func=self.execute_command,
        )
        
        
        check_service_tool = AgentTool(
            name="check_service",
            description="Check the status of a system service",
            properties={
                "service_name": {
                    "type": "string",
                    "description": "The name of the service to check"
                }
            },
            func=self.check_service_status,
        )
        
        list_processes_tool = AgentTool(
            name="list_processes",
            description="List running processes, optionally filtered by a term",
            properties={
                "filter_term": {
                    "type": "string",
                    "description": "Optional term to filter processes by"
                }
            },
            func=self.list_processes,
        )
        
        get_task_stats_tool = AgentTool(
            name="get_task_stats",
            description="Get statistics about RC agent tasks by querying the API endpoint",
            properties={
                "task_id": {
                    "type": "string",
                    "description": "Optional task ID to filter tasks by. If not provided, return all task stats."
                }
            },
            func=self.get_task_stats,
        )
        
        self.RC_tools = AgentTools(tools=[
            get_health_tool, 
            # execute_command_tool,
            check_service_tool,
            list_processes_tool,
            get_task_stats_tool
        ])
        
        if extra_tools:
            self.RC_tools.tools.extend(extra_tools.tools if isinstance(extra_tools, AgentTools) else extra_tools)
            
        if self.RC_tools.tools:
            self.tool_config = {'tool': self.RC_tools, 'toolMaxRecursions': 2}

    def _initialize_prompt_template(self, options: RCAgentOptions) -> None:
        """
        Initialize the system prompt template for the agent.
        """
        # Generate tool information string
        tools_str = self._generate_tools_description()
        
        # Default prompt template for compute resources
        default_template = f"""
        # Role: {{{{name}}}} - Compute Resource Administrator

        ## Agent Information
        {{{{description}}}}
        
        ## Capabilities
        {{{{capabilities}}}}
        
        ## Available Tools
        {{{{tools}}}}
        
        ## Instructions
        - I am a specialized agent for managing and monitoring compute resources
        - I can analyze system information and provide diagnostics
        - I can execute verified commands on the underlying system when permitted
        - I always verify command safety before execution
        - I prioritize system stability and security in all operations
        {{{{additional_instructions}}}}
        
        ## Command Guidelines
        - When executing commands, I first verify they are not potentially harmful
        - I provide clear explanations about command purposes and results
        - I recommend safer alternatives when risky commands are requested
        - I can help diagnose system issues and suggest solutions
        - If the resposnes from the tools have the ID information for examples (job_id,..), Please show them to the users.
        
        ## Response Format
        - I provide concise, accurate information about system status
        - For monitoring data, I present it in a clear, structured format
        - When errors occur, I explain the likely cause and recommend fixes
        - I use technical terms appropriately with explanations when needed
        - All jobs I do is post to an Queue and wait for the result.
        """
        
        # Use custom template if provided
        self.prompt_template = options.prompt_templates.get('default', default_template)
        self.system_prompt = ""
        
        # Generate capabilities and additional instructions based on available tools
        capabilities = self._generate_capabilities_description()
        additional_instructions = self._generate_additional_instructions()
        
        # Set up custom variables for template
        self.custom_variables = {
            "name": self.name,
            "description": self.description or "I am a Compute Resource Agent specialized in system monitoring, command execution, and resource management.",
            "capabilities": capabilities,
            "tools": tools_str,
            "additional_instructions": additional_instructions
        }
        
        # Override with custom prompt if provided
        if options.custom_system_prompt:
            self.set_system_prompt(
                options.custom_system_prompt.get('template'),
                options.custom_system_prompt.get('variables')
            )
    
    def _generate_tools_description(self) -> str:
        """
        Generate a formatted description of all available tools.
        
        Returns:
            str: A formatted string describing all tools
        """
        if not hasattr(self, 'RC_tools') or not self.RC_tools or not self.RC_tools.tools:
            return "No tools available."
            
        tools_description = []
        for tool in self.RC_tools.tools:
            # Format property descriptions if available
            properties_desc = ""
            if hasattr(tool, 'properties') and tool.properties:
                property_items = []
                for prop_name, prop_info in tool.properties.items():
                    prop_type = prop_info.get('type', 'string')
                    prop_desc = prop_info.get('description', '')
                    property_items.append(f"    - {prop_name} ({prop_type}): {prop_desc}")
                
                if property_items:
                    properties_desc = "\n" + "\n".join(property_items)
            
            # Use func_description instead of description
            tool_desc = tool.func_description if hasattr(tool, 'func_description') else "No description available"
            
            # Add the tool description
            tools_description.append(f"- {tool.name}: {tool_desc}{properties_desc}")
            
        return "\n".join(tools_description)
    
    def _generate_capabilities_description(self) -> str:
        """
        Generate a description of capabilities based on available tools.
        
        Returns:
            str: A formatted string describing capabilities
        """
        capabilities = [
            "- System health monitoring and resource utilization tracking",
            "- System diagnostics and troubleshooting"
        ]
        
        # Add tool-specific capabilities if tools exist
        if hasattr(self, 'RC_tools') and self.RC_tools and self.RC_tools.tools:
            tool_names = [tool.name for tool in self.RC_tools.tools]
            
            if any(name in ["execute_command", "run_command"] for name in tool_names):
                capabilities.append("- Command execution with security verification")
                
            if any(name in ["check_service", "check_service_status"] for name in tool_names):
                capabilities.append("- Service status checking and management")
                
            if any(name in ["list_processes", "ps"] for name in tool_names):
                capabilities.append("- Process monitoring and management")
                
            if any(name in ["monitor_resources", "get_system_info"] for name in tool_names):
                capabilities.append("- Real-time system resource monitoring")
                
        return "\n".join(capabilities)
    
    def _generate_additional_instructions(self) -> str:
        """
        Generate additional instructions based on available tools.
        
        Returns:
            str: A formatted string with additional instructions
        """
        instructions = []
        
        # Only add instructions for tools that actually exist
        if hasattr(self, 'RC_tools') and self.RC_tools and self.RC_tools.tools:
            tool_names = [tool.name for tool in self.RC_tools.tools]
            
            if any(name in ["monitor_resources", "get_system_info"] for name in tool_names):
                instructions.append("- I can monitor CPU, memory, and disk usage in real-time")
                
            if any(name in ["check_service", "check_service_status"] for name in tool_names):
                instructions.append("- I can check status of services and report their current state")
                
            if any(name in ["list_processes", "ps"] for name in tool_names):
                instructions.append("- I can list running processes and filter them by specific terms")
                
            if any(name in ["get_health"] for name in tool_names):
                instructions.append("- I can perform system health checks to diagnose issues")
                
            if any(name in ["get_task_stats"] for name in tool_names):
                instructions.append("- I can track and report on system task statistics and resource usage")
                
        return "\n".join(instructions)

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for the agent."""
        self.session_id = session_id

    def get_health(self) -> str:
        """
        Get the health status of the RAgent system.

        Returns:
            str: A message indicating the result of the health check operation.
        """
        try:
            # Validate session_id is present
            if not self.session_id:
                return "Error: No session ID available. Please ensure you are in an active session."
                
            # Validate project_id is present
            if not self.project_id:
                Logger.warning("Project ID is missing for health check")
                # Use a default project ID as fallback
                project_id = "default_project"
            else:
                project_id = self.project_id
                
            # Prepare the health check payload
            payload = {
                "type": 1,
                "session_id": self.session_id,
                "project_id": project_id,
                "data": {"time": int(time.time())}
            }
            
            # Fix URL structure - use /agent/task instead of /task
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}"
            Logger.info(f"Getting health status from {url_post_with_key}")
            
            response = requests.post(url_post_with_key, json=payload)
            
            # Log the response for debugging
            Logger.info(f"Health check response status: {response.status_code}")
            Logger.info(f"Health check response text: {response.text[:200]}...")  # Log first 200 chars
            
            # Parse response json, with error handling
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                Logger.error(f"Failed to parse JSON response: {e}")
                return f"Error: Received invalid response from server. Status code: {response.status_code}"
            
            if response.status_code != 200:
                error_msg = response_data.get('message', 'Unknown error')
                Logger.error(f"Health check API error: {error_msg}")
                return f"Error checking health: API returned status {response.status_code} - {error_msg}"
                
            # Extract job ID and return success message
            data = response_data.get('data', {})
            if not data:
                Logger.warning("Health check response missing data field")
                return "Health check initiated but no job information was returned."
                
            job_id = data.get('job_id')
            if not job_id:
                Logger.warning("Health check response missing job_id")
                return "Health check initiated but no job ID was returned."
                
            status = data.get('status', 'processing')
            
            return f"Health check initiated with job ID: {job_id}. Current status: {status}"
        except requests.exceptions.RequestException as e:
            Logger.error(f"Network error during health check: {str(e)}")
            return f"Network error during health check: {str(e)}"
        except Exception as e:
            Logger.error(f"Error checking health: {str(e)}")
            return f"Error checking health: {str(e)}"

    def _verify_command_safety(self, command: str) -> bool:
        """
        Verify the safety of a command before execution.
        
        Args:
            command (str): The command to verify.
            
        Returns:
            bool: True if the command is safe, False otherwise.
        """
        try:
            # Create system prompt for command verification
            system_prompt = """You are a security-focused system administrator. 
            Your job is to analyze shell commands and determine if they are safe to execute.
            
            Safe commands typically:
            1. List files or directories
            2. Display information about the system
            3. Read (but not modify) standard config files
            4. Simple data processing operations
            
            Potentially harmful commands include:
            1. Removing or modifying critical files (rm -rf /, etc.)
            2. Downloading and executing unknown code
            3. Exporting sensitive data
            4. Modifying system configurations
            5. Commands with pipe to bash/shell
            6. Network commands that expose the system
            
            Respond with a clear yes/no verdict on whether the command is safe."""
            
            # Make LLM call to verify command
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Is this command safe to execute? Command: `{command}`\nRespond with only 'yes' or 'no'."}
                ],
                max_tokens=10,
                temperature=0.0,
            )
            
            verdict = response.choices[0].message.content.strip().lower()
            return verdict == 'yes'
        except Exception as e:
            Logger.error(f"Error verifying command safety: {str(e)}")
            return False

    def execute_command(self, command: str) -> str:
        """
        Execute a command on the compute resource.

        Args:
            command (str): The command to execute.

        Returns:
            str: A message indicating the result of the operation.
        """
        try:
            # Verify command safety first
            if not self._verify_command_safety(command):
                return f"Command '{command}' was deemed unsafe and was not executed."
            
            # Prepare the command execution payload
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": command
                }
            }
            
            # Make the API request
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RC"
            Logger.info(f"Executing command via {url_post_with_key}: {command}")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error executing command: {response_data.get('message')}")
                
            # Extract job ID and return success message
            job_id = response_data.get('data', {}).get('job_id')
            status = response_data.get('data', {}).get('status', 'processing')
            
            return f"Command '{command}' execution initiated with job ID: {job_id}. Current status: {status}"
        except Exception as e:
            Logger.error(f"Error executing command: {str(e)}")
            return f"Error executing command: {str(e)}"

    def is_streaming_enabled(self) -> bool:
        """Check if streaming is enabled for this agent."""
        return self.streaming is True

    async def process_request(
        self,
        input_text: str,
        user_id: str,
        session_id: str,
        chat_history: List[ConversationMessage],
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Union[ConversationMessage, AsyncIterable[Any]]:
        try:

            self.update_system_prompt()
            self.set_session_id(session_id)
            system_prompt = self.system_prompt
            # Fetch global conversation history if storage is available
            global_history = []
            if additional_params and 'global_history'  in additional_params:
                global_history = additional_params['global_history']
                Logger.info(f"Retrieved {len(global_history)} global history messages from additional_params")
            
            

            # Add global history context if available
            if global_history:
                global_context = "\n\nGLOBAL CONVERSATION CONTEXT:\n"
                for i, msg in enumerate(global_history):
                    if i >= 10:  # Limit to last 10 messages to avoid token limits
                        break
                    content = msg.content[0].get('text', '') if msg.content else ''
                    global_context += f"{msg.role}: {content}\n"
                system_prompt += global_context



            if self.retriever:
                response = await self.retriever.retrieve_and_combine_results(input_text)
                context_prompt = "\nHere is the context to use to answer the user's question:\n" + response
                system_prompt += context_prompt


            messages = [
                {"role": "system", "content": system_prompt},
                *[{
                    "role": msg.role.lower(),
                    "content": msg.content[0].get('text', '') if msg.content else ''
                } for msg in chat_history],
                {"role": "user", "content": input_text}
            ]


            request_options = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.inference_config.get('maxTokens'),
                "temperature": self.inference_config.get('temperature'),
                "top_p": self.inference_config.get('topP'),
                "stop": self.inference_config.get('stopSequences'),
                "stream": self.streaming,
                "timeout": 20,
            }

            # Add tools configuration if available
            if self.tool_config:
                tools = self.tool_config["tool"] if not isinstance(self.tool_config["tool"], AgentTools) else self.tool_config["tool"].to_openai_format()
                request_options['tools'] = tools
                # Handle tool calling recursively
                final_message = ''
                tool_use =True
                max_recursions = self.tool_config.get('toolMaxRecursions', self.default_max_recursions)
                time_step_call = 0
                while tool_use and max_recursions > 0:
                    time_step_call +=1
                    if self.streaming:
                        #Logger.info(f"Handling streaming response, request_options: {request_options}")
                        finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                        Logger.info(f"the response is : {finish_reason, response}")
                    else:
                        Logger.info(f"Calling tool use for the {time_step_call} times")
                        finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
                        Logger.info(f"Response: {finish_reason, response, tool_use_blocks}")
                    responses = finish_reason, response, tool_use_blocks
                    if tool_use_blocks:
                        if response:
                            request_options['messages'].append({"role": "assistant", "content": response})
                        if not self.tool_config:
                            raise ValueError("No tools available for tool use")
                        if self.tool_config.get('useToolHandler'):
                            tool_response = self.tool_config['useToolHandler'](responses, request_options['messages'])
                        else:
                            tools:AgentTools = self.tool_config["tool"]
                            if self.base_url:
                                tool_response = await tools.tool_handler(AgentProviderType.DEEPINFRA.value, tool_use_blocks, request_options['messages'])
                            else:
                                tool_response = await tools.tool_handler(AgentProviderType.OPENAI.value, tool_use_blocks, request_options['messages'])
                        Logger.info(f"Tool response: {tool_response}")
                        request_options['messages'].extend(tool_response)
                        tool_use = True
                    else:
                        final_message = response if response else ""
                    if finish_reason != 'tool_calls':
                        tool_use = False
                    max_recursions -= 1

                return ConversationMessage(role=ParticipantRole.ASSISTANT.value,  content=[{"text": f"<startagent>[{self.name}] {final_message}<endagent>"}])
            else:
                if self.streaming:
                    finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                else:
                    finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
                
                return ConversationMessage(
                    role = ParticipantRole.ASSISTANT.value,
                    content=[{"text": f"<startagent>[{self.name}] {response}<endagent>"}]
                )
        except Exception as error:
            Logger.error(f"Error in OpenAI API call: {str(error)}")
            raise error

    async def handle_single_response(self, request_options: Dict[str, Any]) -> ConversationMessage:
        try:
            request_options['stream'] = False
            chat_completion = self.client.chat.completions.create(**request_options)

            if not chat_completion.choices:
                raise ValueError('No choices returned from OpenAI API')

            assistant_message = chat_completion.choices[0].message.content
            tools = chat_completion.choices[0].message.tool_calls 
            finish_reason = chat_completion.choices[0].finish_reason
            # tool_calls = {}
            if not isinstance(assistant_message, str) and not isinstance(tools,list):
                raise ValueError('Unexpected response format from OpenAI API')
     

            return finish_reason, assistant_message, tools
        except Exception as error:
            Logger.error(f'Error in OpenAI API call: {str(error)}')
            raise error

    async def handle_streaming_response(self, request_options: Dict[str, Any]) -> ConversationMessage:
        try:
            stream = self.client.chat.completions.create(**request_options)
            accumulated_message = []
            
            # Add agent name prefix for the first chunk
            is_first_chunk = True
            final_tool_calls = {}
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    if is_first_chunk:
                        chunk_content = f"[{self.name}]: {chunk_content}"
                        is_first_chunk = False
                    accumulated_message.append(chunk_content)
                    if self.callbacks:
                        self.callbacks.on_llm_new_token(chunk_content)
                if chunk.choices[0].delta.tool_calls:
                    for tool_call in chunk.choices[0].delta.tool_calls or []:
                        index = tool_call.index
                        if index not in final_tool_calls:
                            final_tool_calls[index] = tool_call
                        final_tool_calls[index].function.arguments += tool_call.function.arguments
            finish_reason = chunk.choices[0].finish_reason        
            return finish_reason, ''.join(accumulated_message) if len(accumulated_message)>0 else None, list(final_tool_calls.values()) if len(final_tool_calls)>0 else None

        except Exception as error:
            Logger.error(f"Error getting stream from OpenAI model: {str(error)}")
            raise error

    def set_system_prompt(self, 
                         template: Optional[str] = None,
                         variables: Optional[TemplateVariables] = None) -> None:
        if template:
            self.prompt_template = template
        if variables:
            self.custom_variables = variables
        self.update_system_prompt()

    def update_system_prompt(self) -> None:
        """Update the system prompt with the current variables."""
        self.custom_variables.update({
            "name": self.name,
            "description": self.description
        })
        all_variables: TemplateVariables = {**self.custom_variables}
        self.system_prompt = self.replace_placeholders(self.prompt_template, all_variables)

    @staticmethod
    def replace_placeholders(template: str, variables: TemplateVariables) -> str:
        import re
        def replace(match):
            key = match.group(1)
            if key in variables:
                value = variables[key]
                return '\n'.join(value) if isinstance(value, list) else str(value)
            return match.group(0)

        return re.sub(r'{{(\w+)}}', replace, template)

            
    def check_service_status(self, service_name: str) -> str:
        """
        Check the status of a system service.
        
        Args:
            service_name (str): The name of the service to check.
            
        Returns:
            str: The status of the requested service.
        """
        # Verify service name safety
        if not self._verify_command_safety(f"systemctl status {service_name}"):
            return f"Service name '{service_name}' validation failed. Please provide a valid service name."
            
        try:
            # Prepare the service check payload
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": f"systemctl status {service_name}"
                }
            }
            
            # Make the API request
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RC"
            Logger.info(f"Checking service status via {url_post_with_key}: {service_name}")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error checking service: {response_data.get('message')}")
                
            return f"Service status check initiated for '{service_name}'. Job ID: {response_data.get('data', {}).get('job_id')}"
        except Exception as e:
            Logger.error(f"Error checking service status: {str(e)}")
            return f"Error checking service status: {str(e)}"
            
    def list_processes(self, filter_term: Optional[str] = None) -> str:
        """
        List running processes, optionally filtered by a term.
        
        Args:
            filter_term (Optional[str]): Term to filter processes by.
            
        Returns:
            str: List of matching processes.
        """
        try:
            # Construct the command based on filter presence
            command = "ps aux" if not filter_term else f"ps aux | grep {filter_term}"
            
            # Verify command safety
            if not self._verify_command_safety(command):
                return f"Process listing command validation failed."
                
            # Prepare the process listing payload
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": command
                }
            }
            
            # Make the API request
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RC"
            Logger.info(f"Listing processes via {url_post_with_key}")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error listing processes: {response_data.get('message')}")
                
            return f"Process listing initiated{' with filter: ' + filter_term if filter_term else ''}. Job ID: {response_data.get('data', {}).get('job_id')}"
        except Exception as e:
            Logger.error(f"Error listing processes: {str(e)}")
            return f"Error listing processes: {str(e)}"

    def get_task_stats(self, task_id: Optional[str] = None) -> str:
        """
        Get statistics about RC agent tasks by querying the API endpoint.
        
        Args:
            thread_id (Optional[str]): The thread ID to filter tasks by. If None, uses current session_id.
            task_id (Optional[str]): A specific task ID to get details for. If provided, only shows information for this task.
            
        Returns:
            str: A formatted report of task statistics or details for a specific task.
        """
        try:
            # Use current session_id if thread_id is not provided
            thread_id = self.session_id
            
            if not thread_id:
                return "Error: No thread ID available. Please provide a thread ID or ensure session is initialized."
            
            # Construct the API URL with authentication
            url = f"{self.api_base_url}/agent/task/rc/stats?authen_key={self.project_auth_token}&thread_id={thread_id}"
            Logger.info(f"Getting task stats from {url}")
            
            # Make the API request
            response = requests.get(url)
            
            # Check for successful response
            if response.status_code != 200:
                return f"Error retrieving task stats: HTTP {response.status_code}"
            
            # Parse the JSON response
            stats_data = response.json()
            
            # Format the response in a human-readable way
            if stats_data.get('code') != 0:
                return f"API Error: {stats_data.get('message', 'Unknown error')}"
            
            data = stats_data.get('data', {})
            
            # If task_id is provided, filter for only that task
            if task_id and task_id != '':
                # Search in completed tasks
                completed_tasks = data.get('list_result_done', [])
                for task in completed_tasks:
                    if task.get('task_id') == task_id:
                        return self._format_single_task(task, "Completed")
                
                # Search in failed tasks
                failed_tasks = data.get('list_failed', [])
                for task in failed_tasks:
                    if task.get('task_id') == task_id:
                        return self._format_single_task(task, "Failed")
                
                # If task not found
                return f"No task found with ID: {task_id}"
            
            # Otherwise, return all tasks (original behavior)
            # Basic stats summary
            summary = f"""
## RC Task Statistics Summary
- **Completion Percentage**: {data.get('completion_percentage', 0)}%
- **Total Tasks**: {data.get('total_tasks', 0)}
- **Completed Tasks**: {data.get('done', 0)}
- **Pending Tasks**: {data.get('pending', 0)}
- **Failed Tasks**: {data.get('failed', 0)}
- **Queue Size**: {data.get('queue_size', 0)}
"""
            
            # Add detailed information about completed tasks
            completed_tasks = data.get('list_result_done', [])
            task_details = ""
            
            if completed_tasks:
                task_details = "\n## Completed Task Details\n"
                
                for i, task in enumerate(completed_tasks, 1):
                    task_id = task.get('task_id', 'Unknown')
                    agent_id = task.get('id', 'Unknown')
                    agent_type = task.get('agent_type', 'Unknown')
                    
                    task_details += f"\n### Task {i}: {task_id}\n"
                    task_details += f"- **Agent ID**: {agent_id}\n"
                    task_details += f"- **Agent Type**: {agent_type}\n"
                    
                    # Add resource usage details if available
                    task_data = task.get('data', {})
                    if task_data:
                        task_details += "- **Resource Usage**:\n"
                        
                        # CPU info
                        cpu_info = task_data.get('cpu', {})
                        if cpu_info:
                            cpu_usage = cpu_info.get('usage', 0)
                            cpu_cores = cpu_info.get('cores', 0)
                            cpu_model = cpu_info.get('model', 'Unknown')
                            task_details += f"  - **CPU**: {cpu_usage:.2f}% usage, {cpu_cores} cores, {cpu_model}\n"
                        
                        # RAM info
                        ram_info = task_data.get('ram', {})
                        if ram_info:
                            ram_total = ram_info.get('total_gb', 0)
                            ram_used = ram_info.get('used_gb', 0)
                            ram_percent = ram_info.get('used_percent', 0)
                            task_details += f"  - **RAM**: {ram_used:.2f}GB / {ram_total:.2f}GB ({ram_percent:.2f}%)\n"
                        
                        # Disk info
                        disk_info = task_data.get('disk', {})
                        if disk_info:
                            disk_total = disk_info.get('total_gb', 0)
                            disk_used = disk_info.get('used_gb', 0)
                            disk_percent = disk_info.get('used_percent', 0)
                            task_details += f"  - **Disk**: {disk_used:.2f}GB / {disk_total:.2f}GB ({disk_percent:.2f}%)\n"
            
            # Add information about failed tasks if any
            failed_tasks = data.get('list_failed', [])
            failed_details = ""
            
            if failed_tasks:
                failed_details = "\n## Failed Task Details\n"
                
                for i, task in enumerate(failed_tasks, 1):
                    task_id = task.get('task_id', 'Unknown')
                    error = task.get('error', 'Unknown error')
                    
                    failed_details += f"\n### Failed Task {i}: {task_id}\n"
                    failed_details += f"- **Error**: {error}\n"
            
            return summary + task_details + failed_details
            
        except Exception as e:
            Logger.error(f"Error retrieving task stats: {str(e)}")
            return f"Error retrieving task stats: {str(e)}"
            
    def _format_single_task(self, task: Dict[str, Any], status: str) -> str:
        """
        Format the details of a single task.
        
        Args:
            task (Dict[str, Any]): The task data to format
            status (str): The status of the task (e.g., "Completed", "Failed")
            
        Returns:
            str: Formatted task details
        """
        task_id = task.get('task_id', 'Unknown')
        agent_id = task.get('id', 'Unknown')
        agent_type = task.get('agent_type', 'Unknown')
        
        result = f"""
## Task Details: {task_id}
- **Status**: {status}
- **Agent ID**: {agent_id}
- **Agent Type**: {agent_type}
"""
        
        # Add error information for failed tasks
        if status == "Failed":
            error = task.get('error', 'Unknown error')
            result += f"- **Error**: {error}\n"
            return result
            
        # Add resource usage details if available for completed tasks
        task_data = task.get('data', {})
        if task_data:
            result += "- **Resource Usage**:\n"
            
            # CPU info
            cpu_info = task_data.get('cpu', {})
            if cpu_info:
                result += "  - **CPU**:\n"
                for key, value in cpu_info.items():
                    if key == 'usage':
                        result += f"    - **{key}**: {value:.2f}%\n"
                    else:
                        result += f"    - **{key}**: {value}\n"
            
            # RAM info
            ram_info = task_data.get('ram', {})
            if ram_info:
                result += "  - **RAM**:\n"
                for key, value in ram_info.items():
                    if 'gb' in key.lower() or 'percent' in key.lower():
                        result += f"    - **{key}**: {value:.2f}\n"
                    else:
                        result += f"    - **{key}**: {value}\n"
            
            # Disk info
            disk_info = task_data.get('disk', {})
            if disk_info:
                result += "  - **Disk**:\n"
                for key, value in disk_info.items():
                    if 'gb' in key.lower() or 'percent' in key.lower():
                        result += f"    - **{key}**: {value:.2f}\n"
                    else:
                        result += f"    - **{key}**: {value}\n"
            
            # Include any additional data fields
            for key, value in task_data.items():
                if key not in ['cpu', 'ram', 'disk']:
                    result += f"- **{key}**: {value}\n"
                    
        return result
