from typing import List, Dict, Optional, Any, Union
import asyncio
from dataclasses import dataclass
from enum import Enum
import json
import random
import time
from rAgent.agents import AgentResponse
from rAgent.utils import Logger
from rAgent.ragents.RXRivalzAgent import RXRivalzAgent

@dataclass
class TweetRestrictions:
    """Restrictions for tweet generation"""
    no_emojis: bool = False
    no_hashtags: bool = False
    no_mentions: bool = False

@dataclass
class TweetAccuracy:
    """Accuracy settings for tweet generation"""
    percentage: int = 60  # Default 60% accuracy
    
    @property
    def description(self) -> str:
        if self.percentage <= 30:
            return "Loosely based on original idea"
        elif self.percentage <= 60:
            return "Moderately faithful to original idea"
        else:
            return "Strictly faithful to original idea"

@dataclass
class TweetThemeKey:
    """Represents a theme/key for tweet generation"""
    key_id: int
    title: str
    description: str
    example_tweet: str
    focus_points: List[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "title": self.title,
            "description": self.description,
            "example_tweet": self.example_tweet,
            "focus_points": self.focus_points or []
        }

class TweetGenerator:
    """
    Handles tweet generation with human-in-the-loop workflow.
    
    This class manages the process of:
    1. Setting tweet generation parameters
    2. Generating theme keys based on original tweet
    3. Generating tweets based on selected keys
    4. Validating tweets against character profiles and restrictions
    5. Posting tweets after user confirmation
    """
    
    def __init__(self, agents: List[RXRivalzAgent]):
        """
        Initialize with a list of RXRivalzAgent instances.
        
        Args:
            agents: List of RXRivalzAgent instances to use for tweet generation
        """
        self.agents = agents
        self.original_tweet = ""
        self.restrictions = TweetRestrictions()
        self.accuracy = TweetAccuracy()
        self.generated_keys = []
        self.selected_key_ids = []
        self.generated_tweets = []
        
        # Assign random agent as coordinator
        if agents:
            self.coordinator = random.choice(agents)
        else:
            raise ValueError("At least one agent must be provided")
    
    def set_original_tweet(self, tweet_text: str) -> None:
        """Set the original tweet idea"""
        self.original_tweet = tweet_text
    
    def set_restrictions(self, restrictions: TweetRestrictions) -> None:
        """Set restrictions for tweet generation"""
        self.restrictions = restrictions
    
    def set_accuracy(self, percentage: int) -> None:
        """Set accuracy percentage for tweet generation"""
        self.accuracy.percentage = max(0, min(100, percentage))
    
    async def generate_tweet_keys(self, num_keys: int = 3) -> List[TweetThemeKey]:
        """
        Generate theme keys based on the original tweet.
        
        Args:
            num_keys: Number of theme keys to generate
            
        Returns:
            List of TweetThemeKey objects
        """
        prompt = f"""
        Based on the following original tweet idea:
        "{self.original_tweet}"
        
        Generate {num_keys} distinct themes or keys for creating tweets. Each key should focus on a different aspect or angle of the original idea.
        
        For each key, provide:
        1. A title (short phrase identifying the key theme)
        2. A description explaining the focus and tone of this theme
        3. An example tweet that demonstrates this key's approach
        4. 3-5 key focus points or elements that define this theme
        
        Format your response as a structured JSON array with {num_keys} objects.
        """
        
        try:
            Logger.info(f"Generating {num_keys} tweet theme keys")
            
            response = await self.coordinator.acompletion(
                messages=[
                    {"role": "system", "content": "You are a social media content strategist specializing in tweet themes."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            content = response.output.content[0].get('text', '')
            
            # Parse JSON response
            try:
                json_data = json.loads(content)
                keys_data = json_data.get("keys", [])
                
                if not keys_data:
                    Logger.error("No keys found in JSON response")
                    return []
                
                # Create TweetThemeKey objects
                theme_keys = []
                for i, key_data in enumerate(keys_data):
                    theme_key = TweetThemeKey(
                        key_id=i+1,
                        title=key_data.get("title", f"Theme {i+1}"),
                        description=key_data.get("description", ""),
                        example_tweet=key_data.get("example_tweet", ""),
                        focus_points=key_data.get("focus_points", [])
                    )
                    theme_keys.append(theme_key)
                
                self.generated_keys = theme_keys
                Logger.info(f"Generated {len(theme_keys)} tweet keys")
                return theme_keys
                
            except json.JSONDecodeError as e:
                Logger.error(f"Failed to parse key generation response as JSON: {str(e)}")
                Logger.error(f"Raw response: {content}")
                return []
                
        except Exception as e:
            Logger.error(f"Error generating tweet keys: {str(e)}")
            return []
    
    def select_keys(self, key_ids: List[int]) -> None:
        """Select which theme keys to use for tweet generation"""
        self.selected_key_ids = key_ids
    
    async def generate_tweets(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Generate tweets based on selected theme keys.
        
        Args:
            count: Number of tweets to generate
            
        Returns:
            List of tweet data dictionaries
        """
        if not self.selected_key_ids:
            Logger.error("No theme keys selected for tweet generation")
            return []
        
        if not self.original_tweet:
            Logger.error("Original tweet not set")
            return []
        
        # Find selected keys
        selected_keys = [key for key in self.generated_keys if key.key_id in self.selected_key_ids]
        if not selected_keys:
            Logger.error("No matching keys found for the selected key IDs")
            return []
        
        try:
            Logger.info(f"Generating {count} tweets with {len(selected_keys)} themes")
            
            # Determine tweets per key
            tweets_per_key = count // len(selected_keys)
            remainder = count % len(selected_keys)
            
            all_tweets = []
            
            # Generate tweets for each key
            for key in selected_keys:
                # Calculate how many tweets for this key
                key_tweet_count = tweets_per_key + (1 if remainder > 0 else 0)
                if remainder > 0:
                    remainder -= 1
                
                if key_tweet_count <= 0:
                    continue
                
                # Create prompt for this key
                prompt = self._create_tweet_generation_prompt(key, key_tweet_count)
                
                # Get agents to use for this key
                key_agents = self._get_agents_for_key(len(self.agents))
                
                # Track successful tweets
                successful_tweets = []
                
                # Try with each agent until we have enough tweets
                for agent in key_agents:
                    if len(successful_tweets) >= key_tweet_count:
                        break
                    
                    try:
                        # Generate tweets with this agent
                        response = await agent.acompletion(
                            messages=[
                                {"role": "system", "content": f"You are a social media specialist writing tweets in the style of: {agent.character_traits}"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.8,
                            response_format={"type": "json_object"}
                        )
                        
                        content = response.output.content[0].get('text', '')
                        
                        # Parse JSON response
                        try:
                            json_data = json.loads(content)
                            tweets_data = json_data.get("tweets", [])
                            
                            if not tweets_data:
                                continue
                            
                            # Add agent and key info to tweets
                            for tweet_data in tweets_data:
                                tweet_data["agent_id"] = agent.agent_id
                                tweet_data["agent_name"] = agent.name
                                tweet_data["character_traits"] = agent.character_traits
                                tweet_data["key_id"] = key.key_id
                                tweet_data["key_title"] = key.title
                                
                                # Basic accuracy assessment
                                tweet_data["accuracy_assessment"] = self._assess_accuracy(
                                    tweet_data["tweet_text"], 
                                    self.original_tweet,
                                    self.accuracy.percentage
                                )
                                
                                successful_tweets.append(tweet_data)
                            
                        except json.JSONDecodeError:
                            Logger.error(f"Failed to parse tweet generation response as JSON from agent {agent.name}")
                            continue
                            
                    except Exception as e:
                        Logger.error(f"Error generating tweets with agent {agent.name}: {str(e)}")
                        continue
                
                # Add successful tweets to overall collection
                all_tweets.extend(successful_tweets[:key_tweet_count])
            
            # Store generated tweets
            self.generated_tweets = all_tweets
            Logger.info(f"Successfully generated {len(all_tweets)} tweets")
            
            return all_tweets
            
        except Exception as e:
            Logger.error(f"Error in tweet generation: {str(e)}")
            return []
    
    def _create_tweet_generation_prompt(self, key: TweetThemeKey, count: int) -> str:
        """Create a prompt for generating tweets based on a specific theme key"""
        restrictions = []
        if self.restrictions.no_emojis:
            restrictions.append("Do not use emojis in the tweets.")
        if self.restrictions.no_hashtags:
            restrictions.append("Do not use hashtags in the tweets.")
        if self.restrictions.no_mentions:
            restrictions.append("Do not include @ mentions in the tweets.")
        
        restrictions_text = " ".join(restrictions) if restrictions else "No content restrictions."
        
        accuracy_description = "loose" if self.accuracy.percentage <= 30 else ("moderate" if self.accuracy.percentage <= 60 else "strict")
        
        return f"""
        Generate {count} unique tweets based on this theme:
        
        THEME: {key.title}
        
        THEME DESCRIPTION: {key.description}
        
        EXAMPLE TWEET: "{key.example_tweet}"
        
        FOCUS POINTS:
        {', '.join(key.focus_points) if key.focus_points else 'N/A'}
        
        ORIGINAL TWEET IDEA: "{self.original_tweet}"
        
        ACCURACY LEVEL: {self.accuracy.percentage}% accuracy ({accuracy_description})
        This means the tweets should match {self.accuracy.percentage}% of the essence, key words, and ideas from the original tweet.
        
        CONTENT RESTRICTIONS: {restrictions_text}
        
        Please output exactly {count} tweets in JSON format as an array of objects.
        Each tweet should be between 200-280 characters.
        
        Format your response as a structured JSON with an array of tweet objects.
        """
    
    def _get_agents_for_key(self, count: int) -> List[RXRivalzAgent]:
        """Get a subset of agents to use for a specific key"""
        # Shuffle to ensure variety
        shuffled = list(self.agents)
        random.shuffle(shuffled)
        return shuffled[:count]
    
    def _assess_accuracy(self, tweet_text: str, original_text: str, target_percentage: int) -> str:
        """
        Assess how closely a tweet matches the original idea.
        Returns a descriptive assessment.
        """
        # Simple implementation - in a real system you might want NLP
        original_words = set(original_text.lower().split())
        tweet_words = set(tweet_text.lower().split())
        
        common_words = original_words.intersection(tweet_words)
        
        if not original_words:
            return "Cannot assess accuracy (no original content)"
        
        match_percentage = len(common_words) / len(original_words) * 100
        
        if match_percentage >= target_percentage * 0.9:  # Within 90% of target
            return f"High accuracy ({match_percentage:.0f}%)"
        elif match_percentage >= target_percentage * 0.7:  # Within 70% of target
            return f"Medium accuracy ({match_percentage:.0f}%)"
        else:
            return f"Low accuracy ({match_percentage:.0f}%)"
    
    async def validate_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a tweet against character profile, restrictions, and accuracy.
        
        Returns:
            Dict with validation results
        """
        tweet_text = tweet_data.get("tweet_text", "")
        if not tweet_text:
            return {"valid": False, "reason": "Tweet text is empty"}
        
        # Check length
        if len(tweet_text) > 280:
            return {
                "valid": False, 
                "reason": f"Tweet exceeds 280 characters (currently {len(tweet_text)})",
                "suggestions": ["Shorten the tweet to fit within 280 characters"]
            }
        
        # Check restrictions
        if self.restrictions.no_emojis and any(ord(c) > 127 for c in tweet_text):
            return {
                "valid": False,
                "reason": "Tweet contains emoji characters which are restricted",
                "suggestions": ["Remove all emojis from the tweet"]
            }
        
        if self.restrictions.no_hashtags and "#" in tweet_text:
            return {
                "valid": False,
                "reason": "Tweet contains hashtags which are restricted",
                "suggestions": ["Remove all hashtags from the tweet"]
            }
        
        if self.restrictions.no_mentions and "@" in tweet_text:
            return {
                "valid": False,
                "reason": "Tweet contains mentions which are restricted",
                "suggestions": ["Remove all @ mentions from the tweet"]
            }
        
        # Check accuracy if it was set as important
        if self.accuracy.percentage > 60:
            accuracy_assessment = tweet_data.get("accuracy_assessment", "")
            if "Low accuracy" in accuracy_assessment:
                return {
                    "valid": False,
                    "reason": f"Tweet accuracy is too low ({accuracy_assessment})",
                    "suggestions": [
                        "Add more keywords from the original tweet",
                        "Include more concepts from the original idea"
                    ]
                }
        
        # All checks passed
        return {"valid": True}
    
    async def post_tweet(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a tweet using the agent system.
        
        Args:
            tweet_data: Dictionary containing tweet information
            
        Returns:
            Dict with posting results
        """
        tweet_text = tweet_data.get("tweet_text", "")
        if not tweet_text:
            return {"success": False, "message": "Tweet text is empty"}
        
        agent_id = tweet_data.get("agent_id")
        agent = None
        
        # Find the corresponding agent
        if agent_id:
            for a in self.agents:
                if a.agent_id == agent_id:
                    agent = a
                    break
        
        # If no specific agent found, use the coordinator
        if not agent:
            agent = self.coordinator
        
        try:
            Logger.info(f"Posting tweet using agent {agent.name}")
            
            # Call the agent's post method
            post_prompt = f"Post the following tweet: {tweet_text}"
            
            response = await agent.acompletion(
                messages=[
                    {"role": "system", "content": "You are a social media manager authorized to post tweets."},
                    {"role": "user", "content": post_prompt}
                ]
            )
            
            content = response.output.content[0].get('text', '')
            
            # Process response and return result
            return {"success": True, "message": "Tweet posted successfully", "response": content}
            
        except Exception as e:
            Logger.error(f"Error posting tweet: {str(e)}")
            return {"success": False, "message": f"Failed to post tweet: {str(e)}"}
    
    async def handle_continue_prompt(self, user_response: str) -> Dict[str, Any]:
        """
        Handle the "Continue to iterate?" prompt from the user.
        
        This method processes user responses to determine whether to:
        1. Generate more tweet options
        2. Proceed with the selected tweet
        3. Cancel the operation
        
        Args:
            user_response: The user's response to the continue prompt
            
        Returns:
            Dict with action to take and any additional data
        """
        user_response = user_response.strip().lower()
        
        # Default response
        result = {
            "action": "unknown",
            "message": "Could not understand your response. Please respond with 'yes', 'no', or 'cancel'."
        }
        
        # Check for positive responses
        if user_response in ["yes", "y", "continue", "iterate", "more"]:
            Logger.info("User chose to continue iteration")
            result = {
                "action": "continue",
                "message": "Continuing to generate more tweet options."
            }
        
        # Check for negative responses
        elif user_response in ["no", "n", "done", "finish", "proceed"]:
            Logger.info("User chose to proceed with current tweets")
            result = {
                "action": "proceed",
                "message": "Proceeding with the current tweets."
            }
        
        # Check for cancel responses
        elif user_response in ["cancel", "stop", "abort", "exit"]:
            Logger.info("User chose to cancel the operation")
            result = {
                "action": "cancel",
                "message": "Operation cancelled."
            }
        
        return result
    
    async def process_continuation(self, continue_response: Dict[str, Any], selected_tweet_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Process the continuation decision and take appropriate action.
        
        Args:
            continue_response: The response from handle_continue_prompt
            selected_tweet_id: ID of a selected tweet (if applicable)
            
        Returns:
            Dict with result of the continuation process
        """
        action = continue_response.get("action", "unknown")
        
        if action == "continue":
            # Generate more tweets with the same parameters
            try:
                # Keep existing keys but generate more tweets
                more_tweets = await self.generate_tweets(count=5)  # Generate 5 more tweets
                
                return {
                    "success": True,
                    "action": "continued",
                    "new_tweets": more_tweets,
                    "message": f"Generated {len(more_tweets)} additional tweets."
                }
            except Exception as e:
                Logger.error(f"Error generating additional tweets: {str(e)}")
                return {
                    "success": False,
                    "action": "error",
                    "message": f"Failed to generate additional tweets: {str(e)}"
                }
                
        elif action == "proceed":
            # Proceed with selected tweet if provided
            if selected_tweet_id is not None and 0 <= selected_tweet_id < len(self.generated_tweets):
                selected_tweet = self.generated_tweets[selected_tweet_id]
                
                # Post the selected tweet
                post_result = await self.post_tweet(selected_tweet)
                
                return {
                    "success": post_result.get("success", False),
                    "action": "posted",
                    "message": post_result.get("message", ""),
                    "tweet_data": selected_tweet
                }
            else:
                return {
                    "success": False,
                    "action": "error",
                    "message": "No valid tweet selected for posting."
                }
                
        elif action == "cancel":
            return {
                "success": True,
                "action": "cancelled",
                "message": "Tweet generation process cancelled."
            }
            
        else:
            return {
                "success": False,
                "action": "unknown",
                "message": "Unrecognized action. Please provide a clear response."
            }