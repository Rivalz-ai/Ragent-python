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
import random
import json
from rAgent.utils import Logger
from rAgent.retrievers import Retriever
from rAgent.utils import AgentTool, AgentTools
from rAgent.types import AgentProviderType
import requests
import random as rd
from abc import ABC, abstractmethod

class SocialMediaClient(ABC):
    """Abstract base class for social media platform clients."""
    
    @abstractmethod
    def post_content(self, content: str, **kwargs) -> Dict[str, Any]:
        """Post content to the social media platform."""
        pass
    
    @abstractmethod
    def refresh_token(self, **kwargs) -> Dict[str, Any]:
        """Refresh authentication token for the platform."""
        pass

class XClient(SocialMediaClient):
    """Client for X (formerly Twitter) platform."""
    
    def __init__(self, access_token: Optional[str] = None, 
                 refresh_token: Optional[str] = None,
                 client_id: Optional[str] = None, 
                 client_secret: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
    
    def post_content(self, content: str, **kwargs) -> Dict[str, Any]:
        """Post content to X platform using X API."""
        # Implementation for direct X API posting would go here
        # This is a placeholder as the current implementation uses a queue API
        return {"status": "success", "id": "placeholder-id"}
    
    def refresh_token(self, **kwargs) -> Dict[str, Any]:
        """Refresh X API OAuth 2.0 access token."""
        if not self.refresh_token or not self.client_id:
            raise ValueError("Refresh token and client ID are required")
            
        url = "https://api.twitter.com/2/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        response = requests.post(url, headers=headers, data=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            if "refresh_token" in data:
                self.refresh_token = data.get("refresh_token")
            return data
        else:       
            raise Exception(f"Failed to refresh token: {response.status_code} - {response.text}")

class RivalzQueueClient(SocialMediaClient):
    """Client for Rivalz queue API."""
    
    def __init__(self, project_auth_token: Optional[str] = None,
                 project_id: Optional[str] = None,
                 api_base_url: str = "https://staging-rome-api-v2.rivalz.ai/agent",
                 x_id: Optional[str] = None):
        self.project_auth_token = project_auth_token
        self.project_id = project_id
        self.api_base_url = api_base_url
        self.x_id = x_id
        self.session_id = ""
    
    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for the client."""
        self.session_id = session_id
    
    def post_content(self, content: str, **kwargs) -> Dict[str, Any]:
        """Queue content for posting via the Rivalz API."""
        if not self.session_id:
            raise ValueError("Session ID is required")
            
        payload = {
            "type": 3,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "data": {"content": content, "x_id": str(self.x_id)}
        }
        url_post_with_key = f"{self.api_base_url}/agent/task?authen_key={self.project_auth_token}"
        Logger.info(f"Posting to {url_post_with_key} with payload: {json.dumps(payload)}")
        
        response = requests.post(url_post_with_key, json=payload)
        response_data = response.json()
        
        if response.status_code != 200:
            raise Exception(f"Error queueing post: {response_data.get('message')}")
            
        return response_data
    
    def refresh_token(self, **kwargs) -> Dict[str, Any]:
        """Not implemented for queue client as it uses project auth token."""
        return {"status": "not_applicable"}

@dataclass
class RXAgentRivalzOptions(AgentOptions):
    """
    Options for configuring the RXRivalzAgent.
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
    default_max_recursions: int = 5
    
    # X API configuration
    xaccesstoken: Optional[str] = None
    xrefreshtoken: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    x_id: str = None
    
    # Account metadata
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    tweet_count: Optional[int] = None
    like_count: Optional[int] = None
    example_post: Optional[str] = None
    style_description: Optional[str] = None
    
    # Rivalz configuration
    project_auth_token: str = None
    project_id: str = None
    api_post: str = "https://staging-rome-api-v2.rivalz.ai/agent"
    
    # Additional configuration fields with default values
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    content_formatting: Dict[str, Any] = field(default_factory=dict)

class RXRivalzAgent(Agent):
    """
    RXRivalzAgent is a specialized agent for interacting with X (formerly Twitter) accounts.
    It queues posts to an external API and provides modular functionality for managing X accounts.
    """

    PERSONALITY_TRAITS = {
        "personality": ["humorous", "serious", "enthusiastic", "skeptical", "optimistic", "calm", "witty", "sarcastic", "confident", "analytical", "empathetic"],
        "tone": ["friendly", "professional", "sarcastic", "casual", "dramatic", "informative", "authoritative", "conversational", "inspirational", "provocative", "thoughtful"],
        "style": ["concise", "eloquent", "slang-heavy", "technical", "colloquial", "formal", "storytelling", "question-based", "data-driven", "metaphorical", "instructional"],
        "perspective": ["newcomer", "expert", "real-world user", "critic", "industry insider", "innovator", "historian", "trendsetter", "skeptical observer", "futurist", "advocate"]
    }

    def __init__(self, options: RXAgentRivalzOptions):
        """
        Initialize the RXRivalzAgent with the provided options.
        """
        super().__init__(options)
        self._validate_options(options)
        
        # Initialize clients and configurations
        self._initialize_llm_client(options)
        self._initialize_social_media_clients(options)
        self._initialize_agent_attributes(options)
        self._initialize_inference_config(options)
        self._initialize_tools(options.extra_tools)
        self._initialize_prompt_template(options)
        
        # Set default content configuration
        self.content_config = options.content_formatting or {
            "max_chars": 280,
            "min_words": 10,
            "max_words": 45,
            "temperature_range": (0.5, 1.0)
        }

    def _validate_options(self, options: RXAgentRivalzOptions) -> None:
        """
        Validate the required options for the agent.
        """
        if not options.api_key:
            raise ValueError("OpenAI API key is required")

    def _initialize_llm_client(self, options: RXAgentRivalzOptions) -> None:
        """
        Initialize the OpenAI client based on the provided options.
        """
        self.client = options.client or OpenAI(api_key=options.api_key, base_url=options.base_url)

    def _initialize_social_media_clients(self, options: RXAgentRivalzOptions) -> None:
        """
        Initialize social media clients for different platforms.
        """
        # X API client for direct interactions with X
        self.x_client = XClient(
            access_token=options.xaccesstoken,
            refresh_token=options.xrefreshtoken,
            client_id=options.client_id,
            client_secret=options.client_secret
        )
        
        # Rivalz Queue client for queueing posts
        self.queue_client = RivalzQueueClient(
            project_auth_token=options.project_auth_token,
            project_id=options.project_id,
            api_base_url=options.api_post,
            x_id=options.x_id
        )

    def _initialize_agent_attributes(self, options: RXAgentRivalzOptions) -> None:
        """
        Initialize agent-specific attributes.
        """
        self.base_url = options.base_url
        self.model = options.model or OPENAI_MODEL_ID_GPT_O_MINI
        self.streaming = options.streaming or False
        self.retriever = options.retriever
        self.default_max_recursions = options.default_max_recursions
        self.session_id = ""
        
        # X account attributes
        self.xaccesstoken = options.xaccesstoken
        self.xrefreshtoken = options.xrefreshtoken
        self.client_id = options.client_id
        self.client_secret = options.client_secret
        self.x_id = options.x_id
        
        # Account metadata
        self.followers_count = options.followers_count
        self.following_count = options.following_count
        self.tweet_count = options.tweet_count
        self.like_count = options.like_count
        self.example_post = options.example_post
        
        # Generate style and description if not provided
        self.style_description = options.style_description or self.create_random_persona()
        self.description = options.description or self.generate_description()
        
        # Rivalz specific attributes
        self.project_auth_token = options.project_auth_token
        self.api_post = options.api_post
        self.project_id = options.project_id

    def _initialize_inference_config(self, options: RXAgentRivalzOptions) -> None:
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
        post_X_tool = AgentTool(
            name="tweet_to_queue",
            description="Add a tweet to the posting queue for a specific account",
            properties={
                "tweet_text": {
                    "type": "string",
                    "description": "The content to be posted as a tweet",
                },
            },
            func=self.post_to_X,
        )
        self.RX_tools = AgentTools(tools=[post_X_tool])
        
        if extra_tools:
            self.RX_tools.tools.extend(extra_tools.tools if isinstance(extra_tools, AgentTools) else extra_tools)
            
        if self.RX_tools.tools:
            self.tool_config = {'tool': self.RX_tools, 'toolMaxRecursions': 2}

    def _initialize_prompt_template(self, options: RXAgentRivalzOptions) -> None:
        """
        Initialize the system prompt template for the agent.
        """
        # Default prompt template with better structure
        default_template = """
        # Role: {{name}}
        
        ## Agent Information
        {{description}}
        
        ## Style and Personality
        My writing style: {{style_description}}
        
        ## Platform Information
        I'm a social media agent specialized for X (formerly Twitter), where content is limited to 280 characters.
        
        ## Instructions
        - Provide concise, engaging responses suitable for X platform
        - Maintain the assigned personality and tone
        - Stay within character limits (280 characters)
        - If asked to post something to X, I can use the tweet_to_queue tool

        ## Examples
        Sample post: {{example_post}}
        
        ## Guidelines
        - Be helpful, accurate, and engaging
        - Stay on-topic and provide valuable insights
        - Use appropriate tone based on the conversation context
        - Avoid sensitive topics unless directly relevant to the query
        """
        
        # Use custom template if provided
        self.prompt_template = options.prompt_templates.get('default', default_template)
        self.system_prompt = ""
        
        # Set up custom variables for template
        self.custom_variables = {
            "name": self.name,
            "description": self.description,
            "style_description": self.style_description,
            "example_post": self.example_post or "Example post not provided",
            "xaccesstoken": self.xaccesstoken
        }
        
        # Override with custom prompt if provided
        if options.custom_system_prompt:
            self.set_system_prompt(
                options.custom_system_prompt.get('template'),
                options.custom_system_prompt.get('variables')
            )

    def post_to_X(self, tweet_text: str) -> str:
        """
        Queue a tweet for posting via the external API.

        Args:
            tweet_text (str): The content of the tweet.

        Returns:
            str: A message indicating the result of the operation.
        """
        try:
            # Set the current session ID to the queue client
            self.queue_client.set_session_id(self.session_id)
            
            # Paraphrase the content for uniqueness
            content = self.paraphrase(tweet_text)
            
            # Post to queue via the client
            response_data = self.queue_client.post_content(content)
            
            # Extract job ID and return success message
            job_id = response_data.get('data', {}).get('job_id')
            return f"ADDED to Queues with ID {job_id}. You can check its status in the sidebar."
        except Exception as e:
            Logger.error(f"Error queueing post: {str(e)}")
            return f"Error adding tweet to queue: {str(e)}"

    def paraphrase(self, content: str) -> str:
        """
        Generate a paraphrased version of the given content.

        Args:
            content (str): The original content.

        Returns:
            str: The paraphrased content.
        """
        persona = self.style_description
        description = self.description
        example_post = self.example_post
        
        # Generate random word count within configured range
        number_words = random.randint(
            self.content_config.get('min_words', 10),
            self.content_config.get('max_words', 45)
        )
        
        # Generate paraphrased content
        response = self._generate_paraphrase(content, persona, description, example_post, number_words)
        
        # Check if response is within character limit, if not, shorten it
        max_chars = self.content_config.get('max_chars', 280)
        return response if len(response) <= max_chars else self._shorten_response(response, persona, description, example_post, max_chars)

    def _generate_paraphrase(self, content: str, persona: str, description: str, example_post: str, number_words: int) -> str:
        """
        Helper function to generate a paraphrased version of the content.
        """
        # Create system prompt for paraphrasing
        system_prompt = f"""You are a skilled social media writer with the following persona: {persona}.
        
        You're writing for an account with this description: {description}
        
        Here's an example of the account's typical post: "{example_post or 'No example available'}"
        
        Your task is to paraphrase or generate a new post based on the provided content, maintaining the persona's style and tone.
        """
        
        # Get temperature from configured range
        temp_range = self.content_config.get('temperature_range', (0.5, 1.0))
        temperature = rd.uniform(temp_range[0], temp_range[1])
        
        # Make LLM call
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Paraphrase or generate a new post with approximately {number_words} words that's under 280 characters:\n\n\"\"\"{content}\"\"\""}
            ],
            max_tokens=90,
            temperature=temperature,
        )
        
        return response.choices[0].message.content

    def _shorten_response(self, response: str, persona: str, description: str, example_post: str, max_chars: int = 280) -> str:
        """
        Helper function to shorten a response to fit within character limit.
        """
        system_prompt = f"""You are a skilled social media writer with the following persona: {persona}.
        
        You're writing for an account with this description: {description}
        
        Your task is to shorten the provided content to strictly under {max_chars} characters while preserving the core message and tone.
        """
        
        return self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": response},
                {"role": "user", "content": f"Please shorten the above content to strictly under {max_chars} characters while maintaining its core message."}
            ],
            max_tokens=60,
            temperature=rd.uniform(0.5, 0.8),  # Use lower temperature for shortening
        ).choices[0].message.content

    def set_session_id(self, session_id: str) -> None:
        """Set the session ID for the agent and its queue client."""
        self.session_id = session_id
        self.queue_client.set_session_id(session_id)

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

    import requests

    def refresh_access_token(self):
        """
        Refresh the Twitter API OAuth 2.0 access token using a refresh token.

        Args:
            refresh_token (str): The refresh token obtained during initial OAuth flow.
            client_id (str): Your Twitter API OAuth 2.0 client ID.
            client_secret (str, optional): Your Twitter API OAuth 2.0 client secret, if required.

        Returns:
            dict: A dictionary containing the new access token and refresh token.
        """
        url = "https://api.twitter.com/2/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # Prepare the payload with required parameters
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.xrefreshtoken,
            "client_id": self.client_id
        }
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        # Make the POST request to the token endpoint
        response = requests.post(url, headers=headers, data=payload)
        
        if response.status_code == 200:
            self.update_access_token(response.json())
            return 200
        else:       
            raise Exception(f"Failed to refresh token: {response.status_code} - {response.text}")


    def create_random_persona(self) -> Dict[str, str]:
        #keywords = self.generate_keywords(content)
        return json.dumps({
            "agent_name": self.name,
            "personality": random.choice(self.PERSONALITY_TRAITS["personality"]),
            "tone": random.choice(self.PERSONALITY_TRAITS["tone"]),
            "style": random.choice(self.PERSONALITY_TRAITS["style"]),
            "perspective": random.choice(self.PERSONALITY_TRAITS["perspective"]),
            #"extra_keyword": keywords  # Thêm từ khóa ngẫu nhiên
        })
    
    def generate_keywords(self, content:str) -> str:
        prompt = str("Generate 10 topic (each topic <3 words) for the following content:\n\n " + content) 
        response =  self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
            {"role": "system", "content": "Provide output in valid JSON format. The data should be like this ." +json.dumps({"keywords": ["keyword1", "keyword2", "keyword3"]})},
            {"role": "user", "content": prompt},
            
        ],
            response_format={"type":"json_object"},
            max_tokens=100,
            temperature=1.0,
            timeout=20,
        ).choices[0].message.content
        try:
            index  = random.randint(0,9)
            return json.loads(response)['keywords'][index]
        except json.JSONDecodeError:
            return response[:10]
    
    def generate_description(self)->str:
        if self.description is None and self.followers_count is not None:
            default = f"""Social media (Twitter/X) agent with X_ID is {self.x_id}.\n\n
                        The agent has {self.followers_count} followers, follows {self.following_count} accounts, and has made {self.tweet_count} tweets.\n\n
                        The agent has liked {self.like_count} tweets and has an example post that reads: {self.example_post}.\n\n"""
            
            if self.followers_count < 1000:
                return default + "I am a new agent with a small following."
            elif self.followers_count < 10000:
                return default+"I am a growing agent with a moderate following."
            else:
                return default+"I am a popular agent with a large following."
        return "Social media (Twitter/X) agent"

    def reset_persona(self, options: Optional[Dict[str, Any]] = None) -> None:
        """
        Reset the agent's persona with optional custom attributes.
        
        Args:
            options (Optional[Dict[str, Any]]): Custom persona options
        """
        # Generate new random persona traits if not specified
        persona = {
            "personality": options.get("personality") or random.choice(self.PERSONALITY_TRAITS["personality"]),
            "tone": options.get("tone") or random.choice(self.PERSONALITY_TRAITS["tone"]),
            "style": options.get("style") or random.choice(self.PERSONALITY_TRAITS["style"]),
            "perspective": options.get("perspective") or random.choice(self.PERSONALITY_TRAITS["perspective"])
        }
        
        # Set the new style description
        self.style_description = json.dumps(persona)
        
        # Update description if provided
        if options and "description" in options:
            self.description = options["description"]
        
        # Update the system prompt with new persona
        self.update_system_prompt()
        
        Logger.info(f"{self.name}: Persona reset with new traits: {persona}")
        
        return persona

    def optimize_content_for_platform(self, content: str, platform: str = "x") -> str:
        """
        Optimize content for a specific platform's requirements and best practices.
        
        Args:
            content (str): The original content to optimize
            platform (str): The target platform (default: "x" for Twitter/X)
            
        Returns:
            str: Optimized content for the target platform
        """
        if platform.lower() == "x":
            # X-specific optimizations
            max_chars = 280
            
            # Create a platform-specific prompt
            platform_prompt = f"""
            Optimize the following content for X (formerly Twitter), following these guidelines:
            1. Maximum 280 characters
            2. Make it engaging and shareable
            3. Include relevant hashtags if appropriate
            4. Use the agent's established tone: {json.loads(self.style_description)['tone']}
            5. Maintain the core message while optimizing for engagement
            
            Original content: {content}
            """
            
            response = self.client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {"role": "system", "content": "You are a social media optimization expert specializing in X platform."},
                    {"role": "user", "content": platform_prompt}
                ],
                max_tokens=120,
                temperature=0.7,
            )
            
            result = response.choices[0].message.content
            
            # Ensure it's within character limit
            if len(result) > max_chars:
                result = self._shorten_response(result, self.style_description, self.description, self.example_post, max_chars)
                
            return result
        else:
            # Generic optimization for other platforms
            return content

    async def generate_content_variations(self, original_content: str, count: int = 3) -> List[str]:
        """
        Generate multiple variations of content with the same core message.
        
        Args:
            original_content (str): The original content to create variations from
            count (int): Number of variations to generate (default: 3)
            
        Returns:
            List[str]: List of content variations
        """
        if count < 1:
            return [original_content]
            
        persona = self.style_description
        description = self.description
        
        variations_prompt = f"""
        Generate {count} unique variations of the following content. 
        Each variation should:
        1. Maintain the same core message
        2. Be under 280 characters
        3. Match the agent's persona: {persona}
        4. Be distinct from each other in wording and structure
        
        Original content: {original_content}
        """
        
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": f"You are a social media content creator for an account with this description: {description}"},
                {"role": "user", "content": variations_prompt}
            ],
            max_tokens=300,
            temperature=0.9,
        )
        
        # Parse variations from response (expecting numbered list)
        variations_text = response.choices[0].message.content
        variations = []
        
        # Extract numbered variations
        import re
        pattern = r'\d+\.\s*(.*?)(?=\d+\.|$)'
        matches = re.findall(pattern, variations_text, re.DOTALL)
        
        if matches:
            variations = [match.strip() for match in matches]
        
        # If parsing failed, split by newlines and try to extract meaningful content
        if not variations:
            variations = [line.strip() for line in variations_text.split('\n') if line.strip() and not line.strip().startswith('Original content:')]
        
        # Ensure we have the requested number of variations
        while len(variations) < count:
            variations.append(self.paraphrase(original_content))
            
        # Limit to requested count
        return variations[:count]

    def analyze_engagement_potential(self, content: str) -> Dict[str, Any]:
        """
        Analyze content for potential engagement metrics.
        
        Args:
            content (str): Content to analyze
            
        Returns:
            Dict[str, Any]: Analysis results including engagement metrics
        """
        # Create an analysis prompt
        analysis_prompt = f"""
        Analyze the following post for X (formerly Twitter) and predict its engagement potential.
        Provide scores from 1-10 for these metrics:
        - Shareability: How likely users will retweet/share this content
        - Engagement: How likely users will interact (likes, replies)
        - Clarity: How clear and understandable the message is
        - Originality: How unique or fresh the content is
        - Topic relevance: How relevant the topic is to current trends
        
        Based on these scores, identify:
        1. Strengths of the post
        2. Areas for improvement
        3. Overall engagement prediction (low/medium/high)
        
        Post: {content}
        """
        
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "You are a social media analytics expert. Respond in JSON format with numeric scores and brief text analysis."},
                {"role": "user", "content": analysis_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.3,
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            return result
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "error": "Failed to parse analysis",
                "raw_response": response.choices[0].message.content,
                "overall_prediction": "unknown"
            }

    def suggest_optimal_posting_time(self, content_theme: str) -> Dict[str, Any]:
        """
        Suggest optimal posting times based on content theme and audience patterns.
        
        Args:
            content_theme (str): Theme or category of the content
            
        Returns:
            Dict[str, Any]: Suggested posting times with reasoning
        """
        # Create a prompt for suggesting optimal posting times
        time_prompt = f"""
        Based on typical X (Twitter) engagement patterns and the following content theme,
        suggest the optimal posting time(s) in a structured format.
        
        Content theme: {content_theme}
        
        Include:
        1. Best day(s) of week
        2. Best time(s) of day (in ET/Eastern Time)
        3. Reasoning for the recommendation
        4. Alternative time(s) for global audience
        """
        
        response = self.client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "You are a social media timing optimization expert. Respond in JSON format."},
                {"role": "user", "content": time_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.4,
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            return result
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "best_days": ["Wednesday", "Thursday"],
                "best_times": ["12:00 PM ET", "5:00 PM ET"],
                "reasoning": "Default recommendation based on typical engagement patterns",
                "alternative_times": ["9:00 AM ET", "8:00 PM ET"]
            }

    # Factory method for creating specialized versions of the agent
    @classmethod
    def create_specialized(cls, specialization: str, options: RXAgentRivalzOptions) -> 'RXRivalzAgent':
        """
        Factory method to create specialized versions of RXRivalzAgent.
        
        Args:
            specialization (str): Type of specialization (e.g., 'news', 'marketing', 'support')
            options (RXAgentRivalzOptions): Base configuration options
            
        Returns:
            RXRivalzAgent: Specialized agent instance
        """
        # Specialized prompt templates by type
        specialized_templates = {
            "news": """
            # Role: {{name}} - News Content Specialist
            
            ## Agent Information
            {{description}}
            
            ## Style and Personality
            My writing style: {{style_description}}
            
            ## Platform Information
            I'm a news-focused social media agent for X (formerly Twitter), where content is limited to 280 characters.
            
            ## Instructions
            - Provide concise, accurate, and neutral news updates
            - Focus on factual reporting and clarity
            - Include relevant context for news items
            - Cite sources when appropriate
            - Avoid sensationalism while maintaining engagement
            - Stay within character limits (280 characters)
            - If asked to post something to X, I can use the tweet_to_queue tool
            
            ## Examples
            Sample post: {{example_post}}
            
            ## Guidelines
            - Prioritize accuracy and timeliness
            - Present multiple perspectives when relevant
            - Follow journalistic ethics and standards
            - Provide value through information, not just opinions
            - Engage with news-related questions professionally
            """,
            
            "marketing": """
            # Role: {{name}} - Marketing Content Specialist
            
            ## Agent Information
            {{description}}
            
            ## Style and Personality
            My writing style: {{style_description}}
            
            ## Platform Information
            I'm a marketing-focused social media agent for X (formerly Twitter), where content is limited to 280 characters.
            
            ## Instructions
            - Create engaging, persuasive marketing content
            - Highlight benefits and value propositions
            - Use compelling calls-to-action
            - Incorporate persuasive techniques appropriately
            - Maintain brand voice consistency
            - Stay within character limits (280 characters)
            - If asked to post something to X, I can use the tweet_to_queue tool
            
            ## Examples
            Sample post: {{example_post}}
            
            ## Guidelines
            - Focus on customer benefits, not just features
            - Use attention-grabbing openings
            - Incorporate social proof when relevant
            - Create a sense of urgency or exclusivity when appropriate
            - Use emotive language strategically
            """,
            
            "support": """
            # Role: {{name}} - Customer Support Specialist
            
            ## Agent Information
            {{description}}
            
            ## Style and Personality
            My writing style: {{style_description}}
            
            ## Platform Information
            I'm a customer support specialist for X (formerly Twitter), where content is limited to 280 characters.
            
            ## Instructions
            - Provide helpful, empathetic customer support
            - Address concerns with professionalism and care
            - Maintain a positive, solution-oriented approach
            - Escalate complicated issues appropriately
            - Stay within character limits (280 characters)
            - If asked to post something to X, I can use the tweet_to_queue tool
            
            ## Examples
            Sample post: {{example_post}}
            
            ## Guidelines
            - Acknowledge customer concerns promptly
            - Express empathy for their situation
            - Provide clear, actionable solutions
            - Follow up to ensure resolution
            - Maintain a friendly, helpful tone even in difficult situations
            """
        }
        
        # Set specialized template if available
        if specialization in specialized_templates:
            if not options.prompt_templates:
                options.prompt_templates = {}
            options.prompt_templates['default'] = specialized_templates[specialization]
            
            # Adjust persona for the specialization
            if specialization == "news":
                options.style_description = json.dumps({
                    "personality": "analytical",
                    "tone": "informative",
                    "style": "concise",
                    "perspective": "neutral observer"
                })
            elif specialization == "marketing":
                options.style_description = json.dumps({
                    "personality": "enthusiastic",
                    "tone": "persuasive",
                    "style": "engaging",
                    "perspective": "advocate"
                })
            elif specialization == "support":
                options.style_description = json.dumps({
                    "personality": "empathetic",
                    "tone": "helpful",
                    "style": "clear",
                    "perspective": "problem solver"
                })
        
        # Create and return the specialized agent
        return cls(options)