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
class RDAgentOptions(AgentOptions):
    """
    Options for configuring the RDAgent.
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

class RDAgent(Agent):
    """
    RDAgent is a specialized agent for data operations and task monitoring.
    It can perform URL fetching, data processing, and monitor task execution.
    """

    def __init__(self, options: RDAgentOptions):
        super().__init__(options)
        self._validate_options(options)
        self._initialize_llm_client(options)
        self._initialize_agent_attributes(options)
        self._initialize_inference_config(options)
        self._initialize_tools(options.extra_tools)
        self._initialize_prompt_template(options)

    def _validate_options(self, options: RDAgentOptions) -> None:
        if not options.api_key:
            raise ValueError("OpenAI API key is required")
        if not options.project_auth_token:
            raise ValueError("Project authentication token is required")

    def _initialize_llm_client(self, options: RDAgentOptions) -> None:
        """
        Initialize the OpenAI client based on the provided options.
        """
        self.client = options.client or OpenAI(api_key=options.api_key, base_url=options.base_url)

    def _initialize_agent_attributes(self, options: RDAgentOptions) -> None:
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

    def _initialize_inference_config(self, options: RDAgentOptions) -> None:
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
        Configure tools for the agent focused on data operations.
        """
        fetch_url_tool = AgentTool(
            name="fetch_url",
            description="Fetch data from a URL at specified intervals",
            properties={
                "url": {
                    "type": "string",
                    "description": "The URL to fetch data from"
                },
                "interval": {
                    "type": "integer",
                    "description": "Interval in seconds between fetches (default: 60)"
                }
            },
            func=self.fetch_url,
        )
        
        process_json_tool = AgentTool(
            name="process_json",
            description="Process and filter JSON data",
            properties={
                "filter_query": {
                    "type": "string",
                    "description": "JQ-style filter query for JSON processing"
                },
                "input_data": {
                    "type": "string",
                    "description": "Input JSON data or file path"
                }
            },
            func=self.process_json,
        )
        
        analyze_data_tool = AgentTool(
            name="analyze_data",
            description="Analyze data files (CSV, TXT)",
            properties={
                "operation": {
                    "type": "string",
                    "description": "Type of analysis (average, sort, extract)"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the data file"
                },
                "parameters": {
                    "type": "object",
                    "description": "Additional parameters for analysis"
                }
            },
            func=self.analyze_data,
        )
        
        get_task_stats_tool = AgentTool(
            name="get_task_stats",
            description="Get statistics about running tasks",
            properties={
                "task_id": {
                    "type": "string",
                    "description": "Optional task ID to get specific task details"
                }
            },
            func=self.get_task_stats,
        )
        
        self.RD_tools = AgentTools(tools=[
            fetch_url_tool,
            process_json_tool,
            analyze_data_tool,
            get_task_stats_tool
        ])
        
        if extra_tools:
            self.RD_tools.tools.extend(extra_tools.tools if isinstance(extra_tools, AgentTools) else extra_tools)
            
        if self.RD_tools.tools:
            self.tool_config = {'tool': self.RD_tools, 'toolMaxRecursions': 2}

    def _initialize_prompt_template(self, options: RDAgentOptions) -> None:
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
        if not hasattr(self, 'RD_tools') or not self.RD_tools or not self.RD_tools.tools:
            return "No tools available."
            
        tools_description = []
        for tool in self.RD_tools.tools:
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
        if hasattr(self, 'RD_tools') and self.RD_tools and self.RD_tools.tools:
            tool_names = [tool.name for tool in self.RD_tools.tools]
            
            if any(name in ["fetch_url"] for name in tool_names):
                capabilities.append("- URL fetching at specified intervals")
                
            if any(name in ["process_json"] for name in tool_names):
                capabilities.append("- JSON data processing and filtering")
                
            if any(name in ["analyze_data"] for name in tool_names):
                capabilities.append("- Data file analysis (CSV, TXT)")
                
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
        if hasattr(self, 'RD_tools') and self.RD_tools and self.RD_tools.tools:
            tool_names = [tool.name for tool in self.RD_tools.tools]
            
            if any(name in ["fetch_url"] for name in tool_names):
                instructions.append("- I can fetch data from URLs at specified intervals")
                
            if any(name in ["process_json"] for name in tool_names):
                instructions.append("- I can process and filter JSON data using jq-style queries")
                
            if any(name in ["analyze_data"] for name in tool_names):
                instructions.append("- I can analyze data files (CSV, TXT) using various operations")
                
            if any(name in ["get_task_stats"] for name in tool_names):
                instructions.append("- I can provide statistics and details about running tasks")
                
        return "\n".join(instructions)

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for the agent."""
        self.session_id = session_id

    def fetch_url(self, url: str, interval: int = 60) -> str:
        """
        Fetch data from a URL at specified intervals.
        
        Args:
            url (str): The URL to fetch data from
            interval (int): Interval in seconds between fetches
            
        Returns:
            str: Response containing job ID and status
        """
        try:
            payload = {
                "type": 0,
                "interval": interval,
                "session_id": self.session_id,
                "data": {
                    "url": url
                }
            }
            
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}"
            Logger.info(f"Initiating URL fetch from {url} with interval {interval}s")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error fetching URL: {response_data.get('message')}")
                
            job_id = response_data.get('data', {}).get('job_id')
            status = response_data.get('data', {}).get('status', 'processing')
            
            return f"URL fetch job initiated for '{url}' with interval {interval}s. Job ID: {job_id}, Status: {status}"
            
        except Exception as e:
            Logger.error(f"Error in URL fetch: {str(e)}")
            return f"Error in URL fetch: {str(e)}"

    def process_json(self, filter_query: str, input_data: str) -> str:
        """
        Process and filter JSON data using jq-style queries.
        
        Args:
            filter_query (str): The filter query to process JSON
            input_data (str): Input JSON data or file path
            
        Returns:
            str: Job ID and status for the processing task
        """
        try:
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {
                    "cmd": f"jq '{filter_query}' {input_data}"
                }
            }
            
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}"
            Logger.info(f"Processing JSON data with query: {filter_query}")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error processing JSON: {response_data.get('message')}")
                
            return f"JSON processing initiated. Job ID: {response_data.get('data', {}).get('job_id')}"
            
        except Exception as e:
            Logger.error(f"Error in JSON processing: {str(e)}")
            return f"Error in JSON processing: {str(e)}"

    def analyze_data(self, operation: str, file_path: str, parameters: Dict[str, Any] = None) -> str:
        """
        Analyze data files using various operations.
        
        Args:
            operation (str): Type of analysis (average, sort, extract)
            file_path (str): Path to the data file
            parameters (Dict[str, Any]): Additional parameters for analysis
            
        Returns:
            str: Job ID and status for the analysis task
        """
        try:
            cmd = ""
            if operation == "average":
                cmd = f"awk '{{sum+=$1}} END {{print \"Average: \" sum/NR}}' {file_path}"
            elif operation == "sort":
                column = parameters.get('column', 1)
                cmd = f"sort -k{column},{column} -n {file_path}"
            elif operation == "extract":
                columns = parameters.get('columns', "1")
                cmd = f"cut -d',' -f{columns} {file_path}"
            else:
                return f"Unsupported operation: {operation}"
                
            payload = {
                "type": 2,
                "session_id": self.session_id,
                "project_id": self.project_id,
                "data": {"cmd": cmd}
            }
            
            url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}"
            Logger.info(f"Analyzing data with operation: {operation}")
            
            response = requests.post(url_post_with_key, json=payload)
            response_data = response.json()
            
            if response.status_code != 200:
                raise Exception(f"Error in data analysis: {response_data.get('message')}")
                
            return f"Data analysis initiated with operation '{operation}'. Job ID: {response_data.get('data', {}).get('job_id')}"
            
        except Exception as e:
            Logger.error(f"Error in data analysis: {str(e)}")
            return f"Error in data analysis: {str(e)}"

    def get_task_stats(self, task_id: Optional[str] = None) -> str:
        """
        Get statistics about running tasks.
        
        Args:
            task_id (Optional[str]): Specific task ID to get details for
            
        Returns:
            str: Formatted task statistics
        """
        try:
            if not self.session_id:
                return "Error: No session ID available"
                
            url = f"{self.api_base_url}/agent/task/rd/stats?authen_key={self.project_auth_token}&thread_id={self.session_id}"
            Logger.info(f"Getting task stats")
            
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

                return ConversationMessage(role=ParticipantRole.ASSISTANT.value,  content=[{"text": f"<\\startagent>[{self.name}] {final_message}<\\endagent>"}])
            else:
                if self.streaming:
                    finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                else:
                    finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
                
                return ConversationMessage(
                    role = ParticipantRole.ASSISTANT.value,
                    content=[{"text": f"<\\startagent>[{self.name}] {response}<\\endagent>"}]
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