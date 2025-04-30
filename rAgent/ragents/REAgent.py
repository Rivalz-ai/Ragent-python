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
import requests
from dataclasses import dataclass, field
from openai import OpenAI
from rAgent.agents import Agent, AgentOptions
from rAgent.types import (
    ConversationMessage,
    ParticipantRole,
    OPENAI_MODEL_ID_GPT_O_MINI,
    TemplateVariables
)
from rAgent.utils import AgentTool, AgentTools
from rAgent.types import AgentProviderType

@dataclass
class REAgentOptions(AgentOptions):
    """
    Options for configuring the REAgent.
    """
    # OpenAI configuration
    api_key: str = None
    base_url: str = None
    model: Optional[str] = None
    streaming: Optional[bool] = None
    inference_config: Optional[Dict[str, Any]] = None

    # Agent configuration
    custom_system_prompt: Optional[Dict[str, Any]] = None
    retriever: Optional[Any] = None
    client: Optional[Any] = None
    extra_tools: Optional[Union[AgentTools, list[AgentTool]]] = None
    default_max_recursions: int = 2

    # RDAgent specific configuration
    project_auth_token: str = None
    project_id: str = None
    api_base_url: str = "https://staging-rome-api-v2.rivalz.ai/agent"

    # Additional configuration fields with default values
    prompt_templates: Dict[str, str] = field(default_factory=dict)

class REAgent(Agent):
    """
    RDAgent is a specialized agent for data operations and task monitoring.
    It can perform URL fetching, data processing, and monitor task execution.
    """

    def __init__(self, options: REAgentOptions):
        super().__init__(options)
        self._validate_options(options)
        self._initialize_llm_client(options)
        self._initialize_agent_attributes(options)
        self._initialize_inference_config(options)
        self._initialize_tools(options.extra_tools)
        self._initialize_prompt_template(options)

    def _validate_options(self, options: REAgentOptions) -> None:
        if not options.api_key:
            raise ValueError("OpenAI API key is required")
        if not options.project_auth_token:
            raise ValueError("Project authentication token is required")

    def _initialize_llm_client(self, options: REAgentOptions) -> None:
        """
        Initialize the OpenAI client based on the provided options.
        """
        self.client = options.client or OpenAI(api_key=options.api_key, base_url=options.base_url)

    def _initialize_agent_attributes(self, options: REAgentOptions) -> None:
        """
        Initialize agent-specific attributes.
        """
        self.base_url = options.base_url
        self.model = options.model or OPENAI_MODEL_ID_GPT_O_MINI
        self.streaming = options.streaming or False
        self.retriever = options.retriever
        self.default_max_recursions = options.default_max_recursions
        self.session_id = ""

        # RDAgent specific attributes
        self.project_auth_token = options.project_auth_token
        self.api_base_url = options.api_base_url
        self.project_id = options.project_id

    def _initialize_inference_config(self, options: REAgentOptions) -> None:
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
        Configure tools for the agent focused on execution tasks.
        """
        execute_command_tool = AgentTool(
            name="execute_command",
            description="Execute a command on the system",
            properties={
                "command": {
                    "type": "string",
                    "description": "The command to execute on the system",
                },
            },
            func=self.execute_command,
        )

        build_docker_tool = AgentTool(
            name="build_docker",
            description="Build a Docker image from a Dockerfile",
            properties={
                "dockerfile_path": {
                    "type": "string",
                    "description": "Path to the Dockerfile",
                },
                "tag": {
                    "type": "string",
                    "description": "Tag for the Docker image",
                },
                "build_args": {
                    "type": "object",
                    "description": "Optional build arguments for Docker build",
                },
            },
            func=self.build_docker,
        )

        curl_request_tool = AgentTool(
            name="curl_request",
            description="Perform an HTTP request using curl",
            properties={
                "url": {
                    "type": "string",
                    "description": "The URL to send the request to",
                },
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, PUT, DELETE)",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers",
                },
                "data": {
                    "type": "string",
                    "description": "Optional data to send with the request",
                },
            },
            func=self.curl_request,
        )

        fix_bugs_tool = AgentTool(
            name="fix_bugs",
            description="Analyze and fix bugs in code",
            properties={
                "code_path": {
                    "type": "string",
                    "description": "Path to the code file with bugs",
                },
                "error_message": {
                    "type": "string",
                    "description": "Error message or description of the bug",
                },
            },
            func=self.fix_bugs,
        )

        get_task_stats_tool = AgentTool(
            name="get_task_stats",
            description="Get statistics about execution tasks",
            properties={
                "task_id": {
                    "type": "string",
                    "description": "Optional task ID to filter tasks by. If not provided, return all task stats."
                }
            },
            func=self.get_task_stats,
        )

        self.RE_tools = AgentTools(tools=[
            execute_command_tool,
            build_docker_tool,
            curl_request_tool,
            fix_bugs_tool,
            get_task_stats_tool
        ])

        if extra_tools:
            self.RE_tools.tools.extend(extra_tools.tools if isinstance(extra_tools, AgentTools) else extra_tools)

        if self.RE_tools.tools:
            self.tool_config = {'tool': self.RE_tools, 'toolMaxRecursions': 2}

    def _initialize_prompt_template(self, options: REAgentOptions) -> None:
        """
        Initialize the system prompt template for the Execute Resource Agent.
        """
        tools_str = self._generate_tools_description()

        default_template = f"""
        # Role: {{{{name}}}} - Execute Resource Specialist

        ## Agent Information
        {{{{description}}}}

        ## Capabilities
        {{{{capabilities}}}}

        ## Available Tools
        {{{{tools}}}}

        ## Instructions
        - I am a specialized agent for executing tasks and functions.
        - I can execute specified functions with provided arguments.
        - I monitor and report the status of task executions.
        {{{{additional_instructions}}}}

        ## Execution Guidelines
        - I validate function names and arguments before execution.
        - I clearly report execution results and any errors encountered.
        - I provide task IDs (job_id, task_id) for tracking purposes.

        ## Response Format
        - I present execution results clearly and concisely.
        - I highlight any errors or issues encountered during execution.
        - All tasks are queued and results are reported upon completion.
        """

        self.prompt_template = options.prompt_templates.get('default', default_template)
        self.system_prompt = ""

        capabilities = self._generate_capabilities_description()
        additional_instructions = self._generate_additional_instructions()

        self.custom_variables = {
            "name": self.name,
            "description": self.description or "I am an Execute Resource Agent specialized in task execution and monitoring.",
            "capabilities": capabilities,
            "tools": tools_str,
            "additional_instructions": additional_instructions
        }

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
        if not hasattr(self, 'RE_tools') or not self.RE_tools or not self.RE_tools.tools:
            return "No tools available."

        tools_description = []
        for tool in self.RE_tools.tools:
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
            tool_desc = tool.description if hasattr(tool, 'description') else "No description available"

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
            "- Task tracking and monitoring",
        ]

        # Add tool-specific capabilities if tools exist
        if hasattr(self, 'RE_tools') and self.RE_tools and self.RE_tools.tools:
            tool_names = [tool.name for tool in self.RE_tools.tools]

            if any(name in ["execute_command"] for name in tool_names):
                capabilities.append("- Command execution with security verification")

            if any(name in ["build_docker"] for name in tool_names):
                capabilities.append("- Docker image building and management")

            if any(name in ["curl_request"] for name in tool_names):
                capabilities.append("- HTTP requests and API interactions")

            if any(name in ["fix_bugs"] for name in tool_names):
                capabilities.append("- Code analysis and bug fixing")

            if any(name in ["get_task_stats"] for name in tool_names):
                capabilities.append("- Task statistics and monitoring")

        return "\n".join(capabilities)

    def _generate_additional_instructions(self) -> str:
        """
        Generate additional instructions based on available tools.

        Returns:
            str: A formatted string with additional instructions
        """
        instructions = []

        # Only add instructions for tools that actually exist
        if hasattr(self, 'RE_tools') and self.RE_tools and self.RE_tools.tools:
            tool_names = [tool.name for tool in self.RE_tools.tools]

            if any(name in ["execute_command"] for name in tool_names):
                instructions.append("- I can execute commands on the system with security verification")

            if any(name in ["build_docker"] for name in tool_names):
                instructions.append("- I can build Docker images from Dockerfiles")

            if any(name in ["curl_request"] for name in tool_names):
                instructions.append("- I can perform HTTP requests to interact with APIs")

            if any(name in ["fix_bugs"] for name in tool_names):
                instructions.append("- I can analyze code and suggest fixes for bugs")

            if any(name in ["get_task_stats"] for name in tool_names):
                instructions.append("- I can provide statistics and details about running tasks")

        return "\n".join(instructions)

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for the agent."""
        self.session_id = session_id

    def execute_command(self, command: str) -> str:
        """
        Execute a command on the system.

        Args:
            command (str): The command to execute on the system.

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
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RE"
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

    def _verify_command_safety(self, command: str) -> bool:
        """
        Verify if a command is safe to execute.

        Args:
            command (str): The command to verify

        Returns:
            bool: True if the command is safe, False otherwise
        """
        try:
            # Define a system prompt for command safety verification
            system_prompt = """
            You are a security verification assistant. Your task is to determine if a command is safe to execute.

            Unsafe commands include:
            - Commands that could delete or modify important system files (rm -rf /, etc.)
            - Commands that could expose sensitive information (cat /etc/shadow, etc.)
            - Commands that could disrupt system operation (shutdown, reboot, etc.)
            - Commands that could be used for malicious purposes (fork bombs, etc.)

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

    def build_docker(self, dockerfile_path: str, tag: str, build_args: Dict[str, str] = None) -> str:
        """
        Build a Docker image from a Dockerfile.

        Args:
            dockerfile_path (str): Path to the Dockerfile
            tag (str): Tag for the Docker image
            build_args (Dict[str, str]): Optional build arguments

        Returns:
            str: Job ID and status for the Docker build task
        """
        try:
            # Construct the docker build command
            cmd = f"docker build -f {dockerfile_path} -t {tag}"

            # Add build args if provided
            if build_args:
                for key, value in build_args.items():
                    cmd += f" --build-arg {key}={value}"

            # Add the build context (directory containing the Dockerfile)
            dockerfile_dir = os.path.dirname(dockerfile_path)
            cmd += f" {dockerfile_dir or '.'}"

            # Verify command safety
            if not self._verify_command_safety(cmd):
                return f"Docker build command was deemed unsafe and was not executed."

            # Prepare the payload
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": cmd
                }
            }

            # Make the API request
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RE"
            Logger.info(f"Building Docker image: {tag}")

            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()

            if response.status_code != 200:
                raise Exception(f"Error building Docker image: {response_data.get('message')}")

            # Extract job ID and return success message
            job_id = response_data.get('data', {}).get('job_id')

            return f"Docker build initiated for image '{tag}'. Job ID: {job_id}"
        except Exception as e:
            Logger.error(f"Error building Docker image: {str(e)}")
            return f"Error building Docker image: {str(e)}"

    def curl_request(self, url: str, method: str = "GET", headers: Dict[str, str] = None, data: str = None) -> str:
        """
        Perform an HTTP request using curl.

        Args:
            url (str): The URL to send the request to
            method (str): HTTP method (GET, POST, PUT, DELETE)
            headers (Dict[str, str]): Optional HTTP headers
            data (str): Optional data to send with the request

        Returns:
            str: Job ID and status for the curl request task
        """
        try:
            # Construct the curl command
            cmd = f"curl -X {method}"

            # Add headers if provided
            if headers:
                for key, value in headers.items():
                    cmd += f" -H '{key}: {value}'"

            # Add data if provided
            if data:
                cmd += f" -d '{data}'"

            # Add the URL
            cmd += f" '{url}'"

            # Verify command safety
            if not self._verify_command_safety(cmd):
                return f"Curl command was deemed unsafe and was not executed."

            # Prepare the payload
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": cmd
                }
            }

            # Make the API request
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RE"
            Logger.info(f"Performing curl request to {url}")

            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()

            if response.status_code != 200:
                raise Exception(f"Error performing curl request: {response_data.get('message')}")

            # Extract job ID and return success message
            job_id = response_data.get('data', {}).get('job_id')

            return f"Curl request initiated for URL '{url}'. Job ID: {job_id}"
        except Exception as e:
            Logger.error(f"Error performing curl request: {str(e)}")
            return f"Error performing curl request: {str(e)}"

    def fix_bugs(self, code_path: str, error_message: str) -> str:
        """
        Analyze and fix bugs in code.

        Args:
            code_path (str): Path to the code file with bugs
            error_message (str): Error message or description of the bug

        Returns:
            str: Analysis and suggested fixes for the bugs
        """
        try:
            # Read the code file
            cmd = f"cat {code_path}"

            # Verify command safety
            if not self._verify_command_safety(cmd):
                return f"Code reading command was deemed unsafe and was not executed."

            # Prepare the payload to read the code
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": cmd
                }
            }

            # Make the API request to read the code
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}&agent_type=RE"
            Logger.info(f"Reading code file: {code_path}")

            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()

            if response.status_code != 200:
                raise Exception(f"Error reading code file: {response_data.get('message')}")

            # Extract job ID for the code reading task
            job_id = response_data.get('data', {}).get('job_id')

            # Return a message indicating that the bug analysis has been initiated
            return f"Bug analysis initiated for code file '{code_path}'. Job ID: {job_id}. The analysis will include the error message: '{error_message}'"
        except Exception as e:
            Logger.error(f"Error analyzing bugs: {str(e)}")
            return f"Error analyzing bugs: {str(e)}"

    def get_task_stats(self, task_id: Optional[str] = None) -> str:
        """
        Get statistics about running execution tasks.

        Args:
            task_id (Optional[str]): Specific task ID to get details for

        Returns:
            str: Formatted task statistics
        """
        try:
            if not self.session_id:
                return "Error: No session ID available"

            url = f"{self.api_base_url}/agent/task/re/stats?authen_key={self.project_auth_token}&thread_id={self.session_id}"
            Logger.info(f"Getting execution task stats")

            response = requests.get(url)
            if response.status_code != 200:
                return f"Error retrieving task stats: HTTP {response.status_code}"

            stats_data = response.json()
            data = stats_data.get('data', {})

            if task_id:
                for task_list in [data.get('list_result_done', []), data.get('list_failed', [])]:
                    for task in task_list:
                        if task.get('task_id') == task_id:
                            return self._format_task_details(task)
                return f"No task found with ID: {task_id}"

            return self._format_task_summary(data)

        except Exception as e:
            Logger.error(f"Error retrieving task stats: {str(e)}")
            return f"Error retrieving task stats: {str(e)}"

    def _format_task_details(self, task: Dict[str, Any]) -> str:
        """Format details for a single task"""
        status = "Completed" if task.get('data') else "Failed"
        details = f"""
## Task Details
- Task ID: {task.get('task_id', 'Unknown')}
- Status: {status}
- Agent Type: {task.get('agent_type', 'Unknown')}
"""
        if status == "Failed":
            details += f"- Error: {task.get('error', 'Unknown error')}\n"
        return details

    def _format_task_summary(self, data: Dict[str, Any]) -> str:
        """Format summary of all tasks"""
        return f"""
## Task Statistics
- Completion Rate: {data.get('completion_percentage', 0)}%
- Total Tasks: {data.get('total_tasks', 0)}
- Completed: {data.get('done', 0)}
- Pending: {data.get('pending', 0)}
- Failed: {data.get('failed', 0)}
- Queue Size: {data.get('queue_size', 0)}
"""
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