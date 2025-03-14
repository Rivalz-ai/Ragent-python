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
from tweeter_tool import post_tweet, post_reply_tweet, split_post

@dataclass
class RXAgentOptions(AgentOptions):
    api_key: str = None
    base_url: str = None
    model: Optional[str] = None
    streaming: Optional[bool] = None
    inference_config: Optional[Dict[str, Any]] = None
    custom_system_prompt: Optional[Dict[str, Any]] = None
    retriever: Optional[Retriever] = None
    client: Optional[Any] = None
    extra_tools: Optional[Union[AgentTools, list[AgentTool]]] = None
    default_max_recursions: int = 2
    xaccesstoken: str = None



class RXAgent(Agent):
    def __init__(self, options: RXAgentOptions):
        super().__init__(options)
        if not options.api_key:
            raise ValueError("OpenAI API key is required")
        
        if options.client:
            self.client = options.client
        else:
            if options.base_url:
                self.client = OpenAI(api_key=options.api_key,base_url=options.base_url)
            else:
                self.client = OpenAI(api_key=options.api_key)

        self.base_url = options.base_url
        self.model = options.model or OPENAI_MODEL_ID_GPT_O_MINI
        self.streaming = options.streaming or False
        self.retriever: Optional[Retriever] = options.retriever
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
        self.prompt_template = f"""You are a {{name}}.
        {{description}} Provide helpful and accurate information based on your expertise.
        
        When processing requests related to social media posts:
            1.  ANALYZE THE ENTIRE CONVERSATION HISTORY across all agents to understand the full context
            2. Consider previous interactions the user has had with other agents (Health, Travel, etc.)
            3. Use this comprehensive history to create more relevant and personalized content
        
        ----
        
        You will engage in an open-ended conversation, providing helpful and accurate information based on your expertise.
        The conversation will proceed as follows:
            1. The human may ask an initial question or provide a prompt on any topic.
            2. You will provide a relevant and informative response.
            3. The human may then follow up with additional questions or prompts related to your previous response,
          allowing for a multi-turn dialogue on that topic.
            4. Or, the human may switch to a completely new and unrelated topic at any point.
            5. You will seamlessly shift your focus to the new topic, providing thoughtful and coherent responses
          based on your broad knowledge base.
        
        ----

        Throughout the conversation, you should aim to:
            1. Understand the context and intent behind each new question or prompt.
            2. Provide substantive and well-reasoned responses that directly address the query.
            3. Draw insights and connections from your extensive knowledge when appropriate.
            4. Ask for clarification if any part of the question or prompt is ambiguous.
            5. Maintain a consistent, respectful, and engaging tone tailored to the human's communication style.
            6. Seamlessly transition between topics as the human introduces new subjects.
        
            
        ----


        When user asks for a tweet, you should:
            1 If user asks for a tweet, WITHOUT ANY CONTEXT, GLOBAL CONTEXT ONLY ABOUT GREETING you should **ASK** for more information.
            2. If FULL CONVERSATION HISTORY have information for posting to tweet; Base your content on the FULL CONVERSATION HISTORY across all agents
            3. Consider both direct conversations with you and conversations with other agents
            4. Choose the most appropriate approach:
                - Keep original content if it's clear and effective
                - Enhance content based on your style and expertise
                - Ask for clarification if necessary
            5. Please DO NOT PROVIDE THE ACCESS TOKEN IN THE RESPONSE
            6. If the tweet is posted successfully, PROVIDE A RESPONSE confirming the action AND LINK TO THE TWEET.
            7. If the tweet POST FAIL, PROVIDE A RESPONSE with the ERROR AND YOUR SUGGESTION.
        
        ---

        NOTE:    
        GLOBAL CONVERSATION HISTORY IS PROVIDED SEPARATELY FROM YOUR DIRECT CONVERSATION HISTORY.
        """
        self._configure_tools(options.extra_tools)
        self.system_prompt = ""
        self.custom_variables: TemplateVariables = {
            "name": self.name,
            "description": self.description,
            "xaccesstoken": self.xaccesstoken
        }

        if options.custom_system_prompt:
            self.set_system_prompt(
                options.custom_system_prompt.get('template'),
                options.custom_system_prompt.get('variables')
            )

    
    def _configure_tools(self, extra_tools: Optional[Union[AgentTools, list[AgentTool]]]) -> None:
        """Configure the tools available to the lead_agent."""
                # Initialize tools
        post_X_tool = AgentTool(
            name="self_postx",
            description="Post the specific content to a X account.",
            properties = {
                "tweet_text": {
                    "type": "string",
                    "description": "The content of the tweet",
                },
            },
            func=self.post_to_X,
        )
        self.RX_tools = AgentTools(tools=[post_X_tool])

        if extra_tools:
            if isinstance(extra_tools, AgentTools):
                self.RX_tools.tools.extend(extra_tools.tools)
            else:
                self.RX_tools.tools.extend(extra_tools)

        if len(self.RX_tools.tools) >0:
            self.tool_config = {
                'tool': self.RX_tools,
                'toolMaxRecursions': 2,
            }
        


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
                time_step_call = 0
                while tool_use and max_recursions > 0:
                    time_step_call +=1
                    if self.streaming:
                        #Logger.info(f"Handling streaming response, request_options: {request_options}")
                        finish_reason, response, tool_use_blocks = await self.handle_streaming_response(request_options)
                        Logger.info(f"the response is : {finish_reason, response}")

                    else:
                        print(f"Calling tool use for the {time_step_call} times")
                        print(f"Request options: {request_options['messages']}")
                        finish_reason, response, tool_use_blocks = await self.handle_single_response(request_options)
                        print(f"Response: {finish_reason, response, tool_use_blocks}")
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
        self.custom_variables.update({
        "name": self.name,
        "description": self.description,
        "access_token": self.xaccesstoken  # This ensures the current token is used
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
    
    def update_access_token(self, new_token: str) -> None:
        """
        Updates the agent's X access token and refreshes the system prompt
        
        Args:
            new_token (str): The new access token for X API
        """
        if not new_token:
            Logger.warn(f"{self.name}: Attempted to update with empty token - ignoring")
            return
            
        Logger.info(f"{self.name}: Updating access token")
        
        # Update the token
        self.xaccesstoken = new_token
        
        # Update system prompt to incorporate the new token
        self.update_system_prompt()
        
        Logger.info(f"{self.name}: Access token successfully updated")
    
    ## help function
    def post_to_X(self,tweet_text:str) -> str:
        """ Tweet the content text to a X account.
        Args:
        :param tweet_text: Content of the tweet.
        :param access_token: Access token of the X account.
        """
        partTwo = None
        if len(tweet_text) > 280:
            post, partTwo = split_post(tweet_text)
        else:
            post = tweet_text
        first_post_results = post_tweet(post, self.xaccesstoken)
        if first_post_results.status_code != 201:
            Logger.info("Error posting tweet: {}".format(first_post_results.text))
            return f"Post to Twitter failed with error: {first_post_results.text} and status code: {first_post_results.status_code}"
        
        id = first_post_results.json()["data"]["id"]
        Logger.info("Tweet posted with id: {}".format(id))
        if partTwo:
            rest_post_results = post_reply_tweet(partTwo, id, self.xaccesstoken)
            if rest_post_results.status_code != 201:
                Logger.info("Error posting the rest post with error: {}".format(rest_post_results.text))
                return f""""
                Success post apart of the tweet with id: {id}, but the rest failed to post with error: {rest_post_results.text}
                and status code: {rest_post_results.status_code}, track the tweet at https://twitter.com/i/web/status/{id}"""
            id2 = rest_post_results.json()["data"]["id"]
            Logger.info(f"Tweet replied the rest posted. {id2}")
            return f"Tweet posted with id: {id} and replied with id: {id2}, track the tweet at https://twitter.com/i/web/status/{id}"
        return f"Tweet posted success with id: {id}, track the tweet at https://twitter.com/i/web/status/{id}"
        # return "Tweet posted success with id: 123456789, track the tweet at https://twitter.com/i/web/status/123456789"
