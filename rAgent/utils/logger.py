from typing import List, Optional, Dict, Any
import json
import logging
from datetime import datetime
from rAgent.types import ConversationMessage, OrchestratorConfig


class Logger:
    """
    Singleton logger class that provides formatted logging for the rAgent system.
    """
    _instance = None
    _logger = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        config: Optional[Dict[str, bool]] = None,
        logger: Optional[logging.Logger] = None
    ):
        if not hasattr(self, 'initialized'):
            Logger._logger = logger or logging.getLogger(__name__)
            self.initialized = True
        self.config: OrchestratorConfig = config or OrchestratorConfig()

    # Logger access methods
    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get the current logger instance."""
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    @classmethod
    def set_logger(cls, logger: logging.Logger) -> None:
        """Set a custom logger."""
        cls._logger = logger

    # Message formatting
    @classmethod
    def format_message(cls, level: str, message: str) -> str:
        """Format a log message with timestamp."""
        return f"{level} - {message}"

    # Standard logging methods
    @classmethod
    def info(cls, message: str, *args: Any) -> None:
        """Log an info message."""
        formatted_message = cls.format_message("INFO", message)
        cls.get_logger().info(f"ℹ️  {formatted_message}", *args)

    @classmethod
    def warn(cls, message: str, *args: Any) -> None:
        """Log a warning message."""
        formatted_message = cls.format_message("WARN", message)
        cls.get_logger().warning(f"⚠️  {formatted_message}", *args)

    @classmethod
    def error(cls, message: str, *args: Any) -> None:
        """Log an error message."""
        formatted_message = cls.format_message("ERROR", message)
        cls.get_logger().error(f"❌  {formatted_message}", *args)

    @classmethod
    def debug(cls, message: str, *args: Any) -> None:
        """Log a debug message."""
        formatted_message = cls.format_message("DEBUG", message)
        cls.get_logger().debug(f"🐞  {formatted_message}", *args)

    # Specialized formatting
    @classmethod
    def log_header(cls, title: str) -> None:
        """Log a header with the given title."""
        formatted_message = cls.format_message("INFO", f"\n** {title.upper()} **")
        cls.get_logger().info(formatted_message)
        cls.get_logger().info('=' * (len(title) + 6))

    # Conversation logging
    def print_chat_history(
        self,
        chat_history: List[ConversationMessage],
        agent_id: Optional[str] = None
    ) -> None:
        """
        Print the chat history for an agent or classifier.
        
        Args:
            chat_history: List of conversation messages
            agent_id: Optional agent identifier
        """
        is_agent_chat = agent_id is not None
        if ((is_agent_chat and not self.config.LOG_AGENT_CHAT) or 
            (not is_agent_chat and not self.config.LOG_CLASSIFIER_CHAT)):
            return

        title = f"Agent {agent_id} Chat History" if is_agent_chat else 'Classifier Chat History'
        self.log_header(title)

        if not chat_history:
            self.get_logger().info('> - None -')
        else:
            for index, message in enumerate(chat_history, 1):
                role = message.role.upper()
                content = message.content
                
                # Handle different content formats
                text = content[0] if isinstance(content, list) else content
                text = text.get('text', '') if isinstance(text, dict) else str(text)
                
                # Truncate long messages for readability
                trimmed_text = f"{text[:80]}..." if len(text) > 80 else text
                self.get_logger().info(f"> {index}. {role}: {trimmed_text}")
                
        self.get_logger().info('')

    def log_classifier_output(self, output: Any, is_raw: bool = False) -> None:
        """
        Log the classifier output.
        
        Args:
            output: The classifier output
            is_raw: Whether this is raw output or processed
        """
        if ((is_raw and not self.config.LOG_CLASSIFIER_RAW_OUTPUT) or 
            (not is_raw and not self.config.LOG_CLASSIFIER_OUTPUT)):
            return

        self.log_header('Raw Classifier Output' if is_raw else 'Processed Classifier Output')
        self.get_logger().info(output if is_raw else json.dumps(output, indent=2))
        self.get_logger().info('')

    def print_execution_times(self, execution_times: Dict[str, float]) -> None:
        """
        Print execution times for performance monitoring.
        
        Args:
            execution_times: Dictionary of timer names to durations
        """
        if not self.config.LOG_EXECUTION_TIMES:
            return

        self.log_header('Execution Times')
        if not execution_times:
            self.get_logger().info('> - None -')
        else:
            for timer_name, duration in execution_times.items():
                self.get_logger().info(f"> {timer_name}: {duration}s")
        self.get_logger().info('')
