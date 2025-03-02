from typing import Dict, List, Union, AsyncIterable, Optional, Any
from dataclasses import dataclass
from openai import OpenAI
from multi_agent_orchestrator.agents import Agent, AgentOptions
from multi_agent_orchestrator.types import (
    ConversationMessage,
    ParticipantRole,
    OPENAI_MODEL_ID_GPT_O_MINI,
    TemplateVariables
)
from multi_agent_orchestrator.utils import Logger
from multi_agent_orchestrator.retrievers import Retriever
from tools import AgentTool, AgentTools, AgentProviderType


@dataclass
class RXAgentOptions(AgentOptions):
    api_key: str = None
    model: Optional[str] = None
    streaming: Optional[bool] = None
    inference_config: Optional[Dict[str, Any]] = None
    custom_system_prompt: Optional[Dict[str, Any]] = None
    retriever: Optional[Retriever] = None
    client: Optional[Any] = None
    tool_config: Optional[Union[dict[str, Any], AgentTools]] = None
    default_max_recursions: int = 5
    xaccesstoken: str = None



class RXAgent(Agent):
    def __init__(self, options: RXAgentOptions):
        super().__init__(options)
        if not options.api_key:
            raise ValueError("OpenAI API key is required")
        
        if options.client:
            self.client = options.client
        else:
            self.client = OpenAI(api_key=options.api_key)

                
        self.model = options.model or OPENAI_MODEL_ID_GPT_O_MINI
        self.streaming = options.streaming or False
        self.retriever: Optional[Retriever] = options.retriever
        self.tool_config: Optional[dict[str, Any]] = options.tool_config
        self.default_max_recursions = options.default_max_recursions
        self.xaccesstoken = options.xaccesstoken
        # Default inference configuration
        default_inference_config = {
            'maxTokens': 1000,
            'temperature': None,
            'topP': None,
            'stopSequences': None
        }

        if options.inference_config:
            self.inference_config = {**default_inference_config, **options.inference_config}
        else:
            self.inference_config = default_inference_config

        # Initialize system prompt
        self.prompt_template = f"""You are a {self.name}.
        {self.description} Provide helpful and accurate information based on your expertise.
        
        When processing requests related to social media posts:
        - ANALYZE THE ENTIRE CONVERSATION HISTORY across all agents to understand the full context
        - Consider previous interactions the user has had with other agents (Health, Travel, etc.)
        - Use this comprehensive history to create more relevant and personalized content
        
        You will engage in an open-ended conversation, providing helpful and accurate information based on your expertise.
        The conversation will proceed as follows:
        - The human may ask an initial question or provide a prompt on any topic.
        - You will provide a relevant and informative response.
        - The human may then follow up with additional questions or prompts related to your previous response,
          allowing for a multi-turn dialogue on that topic.
        - Or, the human may switch to a completely new and unrelated topic at any point.
        - You will seamlessly shift your focus to the new topic, providing thoughtful and coherent responses
          based on your broad knowledge base.
        Throughout the conversation, you should aim to:
        - Understand the context and intent behind each new question or prompt.
        - Provide substantive and well-reasoned responses that directly address the query.
        - Draw insights and connections from your extensive knowledge when appropriate.
        - Ask for clarification if any part of the question or prompt is ambiguous.
        - Maintain a consistent, respectful, and engaging tone tailored to the human's communication style.
        - Seamlessly transition between topics as the human introduces new subjects.
        
        - After posting a tweet, (you will have a status about posting action) you must provide the details information:
            + If the tweet is posted successfully, you should provide the link to the tweet. Else you should provide the error message.
        When user asks for a tweet, you should:
        1. Base your content on the FULL CONVERSATION HISTORY across all agents
        2. Consider both direct conversations with you and conversations with other agents
        3. Choose the most appropriate approach:
           - Keep original content if it's clear and effective
           - Enhance content based on your style and expertise
           - Ask for clarification if necessary
        4. Use the function to post the tweet to the X account with the provided access token: {self.xaccesstoken}
        
        GLOBAL CONVERSATION HISTORY IS PROVIDED SEPARATELY FROM YOUR DIRECT CONVERSATION HISTORY.
        """

        self.system_prompt = ""
        self.custom_variables: TemplateVariables = {}

        if options.custom_system_prompt:
            self.set_system_prompt(
                options.custom_system_prompt.get('template'),
                options.custom_system_prompt.get('variables')
            )
        


    def is_streaming_enabled(self) -> bool:
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
                "stream": self.streaming
            }

            # Add tools configuration if available
            if self.tool_config:
                tools = self.tool_config["tool"] if not isinstance(self.tool_config["tool"], AgentTools) else self.tool_config["tool"].to_openai_format()
                request_options['tools'] = tools
                # Handle tool calling recursively
                final_message = ''
                tool_use =True
                max_recursions = self.tool_config.get('toolMaxRecursions', self.default_max_recursions)
                
                while tool_use and max_recursions > 0:
                    if self.streaming:
                        Logger.info(f"Handling streaming response, request_options: {request_options}")
                        finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                        Logger.info(f"the response is : {finish_reason, response}")

                    else:
                        finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
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
                            tool_response = await tools.tool_handler(AgentProviderType.OPENAI.value, tool_use_blocks, request_options['messages'])
                        request_options['messages'].extend(tool_response)
                        tool_use = True
                    else:
                        final_message = response if response else ""
                    if finish_reason != 'tool_calls':
                        tool_use = False
                    max_recursions -= 1

                return ConversationMessage(role=ParticipantRole.ASSISTANT.value,  content=[{"text": f"<\startagent>[{self.name}] {final_message}<\endagent>"}])
            else:
                if self.streaming:
                    finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                else:
                    finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
                
                return ConversationMessage(
                    role = ParticipantRole.ASSISTANT.value,
                    content=[{"text": f"<\startagent>[{self.name}] {response}<\endagent>"}]
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
     
            # if tools is not None:
            #     for index, tool in enumerate(tools):
            #         tool_calls[index] = {
            #             "index": index,
            #             "id": tool.id,
            #             "function":{ "name":tool.function.name, "arguments":tool.function.arguments}
            #         }
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