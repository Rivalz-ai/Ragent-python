# python-sdk/core/context.py
from typing import Optional, Dict, Any
from pybars import Compiler
import re
from .types import State

def compose_context(
    state: State,
    template: str,
    templating_engine: Optional[str] = None
) -> str:
    """
    Compose context string by replacing placeholders with state values.

    Args:
        state: State object containing replacement values
        template: Template string with {{key}} placeholders
        templating_engine: Optional template engine ('handlebars' or None)

    Returns:
        str: Template with replaced placeholders

    Example:
        state = {"name": "Alice"}
        template = "Hello {{name}}"
        result = compose_context(state, template)
        # Returns: "Hello Alice"
    """
    # Use handlebars engine if specified
    if templating_engine == "handlebars":
        compiler = Compiler()
        template_fn = compiler.compile(template)
        return template_fn(state)
    
    # Simple replacement using regex
    def replace_match(match):
        key = match.group(0)[2:-2]  # Strip {{ and }}
        return str(state.get(key, ""))
        
    return re.sub(r'{{(\w+)}}', replace_match, template)

def add_header(header: str, body: str) -> str:
    """
    Add header to text body with newline separation.

    Args:
        header: Header text to prepend
        body: Main text content

    Returns:
        str: Combined header and body with newlines

    Example:
        header = "Title"
        body = "Content"
        result = add_header(header, body)
        # Returns: "Title\nContent\n"
    """
    if not body:
        return ""
    header_part = f"{header}\n" if header else header
    return f"{header_part}{body}\n"