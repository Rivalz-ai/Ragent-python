import uuid
import random
from typing import Set

class UniqueNameGenerator:
    # Word lists for rich name generation
    ADJECTIVES = [
        'swift', 'brave', 'bright', 'calm', 'clever', 'bold', 'eager', 'fair',
        'great', 'kind', 'quick', 'wise', 'warm', 'safe', 'free', 'true',
        'pure', 'proud', 'firm', 'keen'
    ]
    
    NOUNS = [
        'ace', 'art', 'bird', 'book', 'code', 'data', 'edge', 'flow', 
        'gate', 'host', 'idea', 'key', 'link', 'mind', 'node', 'path',
        'ring', 'sign', 'time', 'wave'
    ]
    
    TECH_TERMS = [
        'api', 'app', 'bit', 'bot', 'cli', 'cpu', 'git', 'gui',
        'hub', 'lan', 'lib', 'map', 'net', 'orm', 'sdk', 'sql',
        'ssh', 'tls', 'url', 'web'
    ]

    def __init__(self):
        self.used_names: Set[str] = set()
        self.counter = 0

    def generate(self, separator: str = '_') -> str:
        """Generate unique name with numeric suffix if needed"""
        while True:
            adj = random.choice(self.ADJECTIVES)
            noun = random.choice(self.NOUNS)
            tech = random.choice(self.TECH_TERMS)
            
            # Try different combinations
            candidates = [
                f"{adj}{separator}{noun}",
                f"{tech}{separator}{noun}",
                f"{adj}{separator}{tech}",
                f"{noun}{separator}{tech}"
            ]
            
            for name in candidates:
                if name not in self.used_names:
                    self.used_names.add(name)
                    return name
            
            # If all combinations used, add numeric suffix
            self.counter += 1
            name = f"{adj}{separator}{noun}{separator}{self.counter}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name

# Create singleton instance
name_generator = UniqueNameGenerator()
