from typing import Any, Optional, Callable, get_type_hints, Union
import inspect
from functools import wraps
import re
from dataclasses import dataclass
from rAgent.types import ConversationMessage, ParticipantRole
from enum import Enum
import json
from rAgent.utils import Logger
class AgentProviderType(Enum):
    BEDROCK = "BEDROCK"
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"
    DEEPINFRA = "DEEPINFRA"


@dataclass
class PropertyDefinition:
    type: str
    description: str
    enum: Optional[list] = None

@dataclass
class AgentToolResult:
    tool_use_id: str
    content: Any
    func_name: Optional[str]= "default_func"

    def to_anthropic_format(self) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content
        }

    def to_bedrock_format(self) -> dict:
        return {
            "toolResult": {
                "toolUseId": self.tool_use_id,
                "content": [{"text": self.content}]
            }
        }
    def to_openai_format(self) -> dict:
        return {
            "role": "function",
            "name": self.func_name,
            "tool_call_id": self.tool_use_id,
            "content": self.content
        }
    def to_deepinfra_format(self) -> dict:
        return {
        "tool_call_id": self.tool_use_id,
        "role": "tool",
        "content": self.content,
        }

class AgentTool:
    def __init__(self,
                name: str,
                description: Optional[str] = None,
                properties: Optional[dict[str, dict[str, Any]]] = None,
                required: Optional[list[str]] = None,
                func: Optional[Callable] = None,
                enum_values: Optional[dict[str, list]] = None,
                strict: Optional[bool] = True):

        self.name = name
        self.strict = strict
        # Extract docstring if description not provided
        if description is None:
            docstring = inspect.getdoc(func)
            if docstring:
                # Get the first paragraph of the docstring (before any parameter descriptions)
                self.func_description = docstring.split('\n\n')[0].strip()
            else:
                self.func_description = f"Function to {name}"
        else:
            self.func_description = description
        self.enum_values = enum_values or {}

        if not func:
            raise ValueError("Function must be provided")

        # Extract properties from the function if not passed
        self.properties = properties or self._extract_properties(func)
        self.required = required or list(self.properties.keys())
        self.func = self._wrap_function(func)

        # Add enum values to properties if they exist
        for prop_name, enum_vals in self.enum_values.items():
            if prop_name in self.properties:
                self.properties[prop_name]["enum"] = enum_vals

    def _extract_properties(self, func: Callable) -> dict[str, dict[str, Any]]:
        """Extract properties from the function's signature and type hints"""
        # Get function's type hints and signature
        type_hints = get_type_hints(func)
        sig = inspect.signature(func)

        # Parse docstring for parameter descriptions
        docstring = inspect.getdoc(func) or ""
        param_descriptions = {}

        # Extract parameter descriptions using regex
        param_matches = re.finditer(r':param\s+(\w+)\s*:\s*([^:\n]+)', docstring)
        for match in param_matches:
            param_name = match.group(1)
            description = match.group(2).strip()
            param_descriptions[param_name] = description

        properties = {}
        for param_name, param in sig.parameters.items():
            # Skip 'self' parameter for class methods
            if param_name == 'self':
                continue

            param_type = type_hints.get(param_name, Any)

            # Convert Python types to JSON schema types
            type_mapping = {
                int: "integer",
                float: "number",
                str: "string",
                bool: "boolean",
                list: "array",
                dict: "object"
            }

            json_type = type_mapping.get(param_type, "string")

            # Use docstring description if available, else create a default one
            description = param_descriptions.get(param_name, f"The {param_name} parameter")

            properties[param_name] = {
                "type": json_type,
                "description": description
            }

        return properties

    def _wrap_function(self, func: Callable) -> Callable:
        """Wrap the function to preserve its metadata and handle async/sync functions"""
        @wraps(func)
        async def wrapper(**kwargs):
            result = func(**kwargs)
            if inspect.iscoroutine(result):
                return await result
            return result
        return wrapper

    def to_claude_format(self) -> dict[str, Any]:
        """Convert generic tool definition to Claude format"""
        return {
            "name": self.name,
            "description": self.func_description,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": self.required
            }
        }

    def to_bedrock_format(self) -> dict[str, Any]:
        """Convert generic tool definition to Bedrock format"""
        return {
            "toolSpec": {
                "name": self.name,
                "description": self.func_description,
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": self.properties,
                        "required": self.required
                    }
                }
            }
        }

    def to_openai_format(self) -> dict[str, Any]:
        """Convert generic tool definition to OpenAI format"""
        return {
            "type": "function",
            "function": {
                "name": self.name.lower().replace("_tool", ""),
                "description": self.func_description,
                "parameters": {
                    "type": "object",
                    "properties": self.properties,
                    "required": self.required,
                    "additionalProperties": False
                },
                "strict": self.strict # Default to True if not set
            }
        }

class AgentTools:
    def __init__(self, tools:list[AgentTool]):
        self.tools:list[AgentTool] = tools

    async def tool_handler(self, provider_type, response: Any, _conversation: list[dict[str, Any]]) -> Any:

        tool_results = []
        if provider_type == AgentProviderType.OPENAI.value or provider_type == AgentProviderType.DEEPINFRA.value:
            content_blocks = response
        else:
            if not response.content:
                raise ValueError("No content blocks in response")
            content_blocks = response.content

        for block in content_blocks:
            # Determine if it's a tool use block based on platform
            tool_use_block = self._get_tool_use_block(provider_type, block)
            if not tool_use_block:
                continue
            tool_name = ""
            if provider_type == AgentProviderType.BEDROCK.value:
                tool_name = tool_use_block.get("name")
            elif provider_type == AgentProviderType.ANTHROPIC.value:
                tool_name = tool_use_block.name
            elif provider_type == AgentProviderType.OPENAI.value or provider_type == AgentProviderType.DEEPINFRA.value:
                tool_name = tool_use_block.function.name


            tool_id = "" 
            if provider_type == AgentProviderType.BEDROCK.value:
                tool_id = tool_use_block.get("toolUseId")
            elif provider_type == AgentProviderType.ANTHROPIC.value:
                tool_id = tool_use_block.id
            elif provider_type == AgentProviderType.OPENAI.value or provider_type == AgentProviderType.DEEPINFRA.value :
                tool_id = tool_use_block.id

   

            # Get input based on platform
            input_data = None
            if provider_type == AgentProviderType.BEDROCK.value:
                input_data = tool_use_block.get("input", {})
            elif provider_type == AgentProviderType.ANTHROPIC.value:
                input_data = tool_use_block.input
            elif provider_type == AgentProviderType.OPENAI.value or provider_type == AgentProviderType.DEEPINFRA.value:
                input_data = json.loads(tool_use_block.function.arguments)
            Logger.info(f"Processing tool '{tool_name}' with input: {input_data}")

            # Process the tool use
            result = await self._process_tool(tool_name, input_data)

            # Create tool result
            tool_result = AgentToolResult(tool_id, result, tool_name)

            # Format according to platform
            formatted_result = None
            if provider_type == AgentProviderType.BEDROCK.value:
                formatted_result = tool_result.to_bedrock_format()
            elif provider_type == AgentProviderType.ANTHROPIC.value:
                formatted_result = tool_result.to_anthropic_format()
            elif provider_type == AgentProviderType.OPENAI.value:
                formatted_result = tool_result.to_openai_format()
            elif provider_type == AgentProviderType.DEEPINFRA.value:
                formatted_result = tool_result.to_deepinfra_format()

            tool_results.append(formatted_result)

        # Create and return appropriate message format
        if  provider_type ==  AgentProviderType.BEDROCK.value:
            return ConversationMessage(
                role=ParticipantRole.USER.value,
                content=tool_results
            )
        elif provider_type ==  AgentProviderType.ANTHROPIC.value:
            return {
                'role': ParticipantRole.USER.value,
                'content': tool_results
            }
        else:
            return tool_results

    def _get_tool_use_block(self, provider_type:AgentProviderType, block: dict) -> Union[dict, None]:
        """Extract tool use block based on platform format."""
        if provider_type == AgentProviderType.BEDROCK.value and "toolUse" in block:
            return block["toolUse"]
        elif provider_type ==  AgentProviderType.ANTHROPIC.value and block.type == "tool_use":
            return block
        elif provider_type ==  AgentProviderType.OPENAI.value or provider_type ==  AgentProviderType.DEEPINFRA.value:
            return block
        return None

    async def _process_tool(self, tool_name, input_data):
        try:
            tool = next(tool for tool in self.tools if tool.name == tool_name)
            return await tool.func(**input_data)
        except StopIteration:
            return (f"Tool '{tool_name}' not found")

    def to_claude_format(self) -> list[dict[str, Any]]:
        """Convert all tools to Claude format"""
        return [tool.to_claude_format() for tool in self.tools]

    def to_bedrock_format(self) -> list[dict[str, Any]]:
        """Convert all tools to Bedrock format"""
        return [tool.to_bedrock_format() for tool in self.tools]
    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI format"""
        return [tool.to_openai_format() for tool in self.tools]
    
    def to_deepinfra_format(self) -> list[dict[str, Any]]:
        """Convert all tools to Deepinfra format"""
        return [tool.to_openai_format() for tool in self.tools]

