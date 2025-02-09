from rome.utils.name_generator import name_generator
import random
from typing import List
from .types import Action, ActionExample


def compose_action_examples(actions_data: List[Action], count: int) -> str:
    # Each action has List[List[ActionExample]], collect all examples
    all_examples = []
    for action in actions_data:
        all_examples.extend(action.examples)
    
    # Select random examples up to count
    selected_examples = []
    if all_examples:
        num_examples = min(count, len(all_examples))
        selected_examples = random.sample(all_examples, num_examples)
    
    # Format selected examples
    formatted = []
    for example_list in selected_examples:
        example_names = [name_generator.generate() for _ in range(5)]
        lines = []
        
        # Format each message in example list
        for message in example_list:
            text = f"{message.user}: {message.content.text}"
            if message.content.action and message.content.action != "null":
                text += f" ({message.content.action})"
                
            # Replace user placeholders
            for i, name in enumerate(example_names, 1):
                text = text.replace(f"{{{{user{i}}}}}", name)
            lines.append(text)
            
        formatted.append("\n" + "\n".join(lines))

    return "\n".join(formatted)

# def compose_action_examples(actions_data: List[Action], count: int) -> str:
    data = [list(action.examples) for action in actions_data]
    action_examples = []
    length = len(data)
    
    for i in range(count):
        if length == 0:
            break
        action_id = i % length
        examples = data[action_id]
        if examples:
            rand_index = random.randrange(len(examples))
            chosen = examples.pop(rand_index)
            action_examples.append(chosen)
        else:
            continue
        
        if len(examples) == 0:
            data.pop(action_id)
            length -= 1

    formatted = []
    for example in action_examples:
        example_names = [name_generator.generate() for _ in range(5)]
        lines = []
        for message in example:
            text = f"{message.user}: {message.content.text}"
            if message.content.action and message.content.action != "null":
                text += f" ({message.content.action})"
            # Replace placeholders {{userX}}
            for i, ename in enumerate(example_names, 1):
                placeholder = f"{{{{user{i}}}}}"
                text = text.replace(placeholder, ename)
            lines.append(text)
        formatted.append("\n" + "\n".join(lines))

    return "\n".join(formatted)

def format_action_names(actions: List[Action]) -> str:
    shuffled = actions[:]
    random.shuffle(shuffled)
    return ", ".join(action.name for action in shuffled)

def format_actions(actions: List[Action]) -> str:
    shuffled = actions[:]
    random.shuffle(shuffled)
    return ",\n".join(f"{action.name}: {action.description}" for action in shuffled)