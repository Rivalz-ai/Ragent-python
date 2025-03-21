"""
Code for Agents.
"""
from .agent import Agent, AgentOptions, AgentCallbacks, AgentProcessingResult, AgentResponse


try:
    from .lambda_agent import LambdaAgent, LambdaAgentOptions
    from .bedrockllm_agent import BedrockLLMAgent, BedrockLLMAgentOptions
    from .comprehend_filter_agent import ComprehendFilterAgent, ComprehendFilterAgentOptions
    from .chain_agent import ChainAgent, ChainAgentOptions
    _AWS_AVAILABLE = True
except ImportError:
    _AWS_AVAILABLE = False
try:
    from .anthropic_agent import AnthropicAgent, AnthropicAgentOptions
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


try:
    from .openai_agent import OpenAIAgent, OpenAIAgentOptions
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

from .supervisor_agent import SupervisorAgent, SupervisorAgentOptions


__all__ = [
    'Agent',
    'AgentOptions',
    'AgentCallbacks',
    'AgentProcessingResult',
    'AgentResponse',
    'SupervisorAgent',
    'SupervisorAgentOptions'
    ]


if _AWS_AVAILABLE :
    __all__.extend([
        'LambdaAgent',
        'LambdaAgentOptions',
        'BedrockLLMAgent',
        'BedrockLLMAgentOptions',
        'LexBotAgent',
        'LexBotAgentOptions',
        'AmazonBedrockAgent',
        'AmazonBedrockAgentOptions',
        'ComprehendFilterAgent',
        'ComprehendFilterAgentOptions',
        'ChainAgent',
        'ChainAgentOptions',
        'BedrockTranslatorAgent',
        'BedrockTranslatorAgentOptions',
        'BedrockInlineAgent',
        'BedrockInlineAgentOptions',
        'BedrockFlowsAgent',
        'BedrockFlowsAgentOptions'
    ])


if _ANTHROPIC_AVAILABLE:
    __all__.extend([
        'AnthropicAgent',
        'AnthropicAgentOptions'
    ])


if _OPENAI_AVAILABLE:
    __all__.extend([
            'OpenAIAgent',
            'OpenAIAgentOptions'
        ])
