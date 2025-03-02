# Function for splitting up posts that are too long for twitter.
from multi_agent_orchestrator.utils import Logger
from tools import AgentTools, AgentTool
import requests
def split_post(text):
    """
    Split a post that is too long for Twitter into two parts.
    The first part will be under 277 characters (leaving room for '...').
    
    Args:
        text: The text to split
    
    Returns:
        tuple: (first_part, second_part) where first_part is <= 280 chars
    """
    Logger.info("Splitting post that is too long for Twitter.")
    
    # If the text is already within limits, return it as is
    if len(text) <= 280:
        return text, ""
    
    # Split the text into sentences
    # We'll consider '.', '!', and '?' as sentence endings
    sentence_endings = ['. ', '! ', '? ']
    split_points = []
    
    for ending in sentence_endings:
        positions = [i + len(ending) for i in range(len(text)) 
                    if text.startswith(ending, i)]
        split_points.extend(positions)
    
    # Add the position after the last character as a potential split point
    split_points.append(len(text))
    # Sort the split points
    split_points.sort()
    
    # Find the last sentence break that keeps the first part under 277 characters
    first_part = text
    second_part = ""
    
    for pos in split_points:
        if pos <= 277:
            first_part = text[:pos].strip()
            second_part = text[pos:].strip()
        else:
            break
    
    # If we couldn't find a suitable sentence break, just cut at 277 chars
    if len(first_part) > 277:
        first_part = text[:274].strip()  # 274 + 3 for '...' = 277
        second_part = text[274:].strip()
    
    # Add '...' to the first part
    first_part += "..."
    
    # If second part is still too long, set it to empty string
    if len(second_part) > 280:
        Logger.info("Second part is still too long, discarding it.")
        second_part = ""
    
    return first_part, second_part


def post_tweet(tweet_text, access_token):
    """
    Function to post a tweet using the current access token.
    :param tweet_text: The text of the tweet.
    :param access_token: The access token to use for posting.
    """
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": tweet_text
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    # Nếu đăng tweet thành công (HTTP 201 Created)
    if response.status_code == 201:
        Logger.info("Tweet success!")
        Logger.info(f"Response: {response.json()}")
    else:
        Logger.error(f"Error tweet: {response.status_code}")
        Logger.error(f"Detail: {response.text}")
    
    return response


def post_reply_tweet(tweet_text, in_reply_to_tweet_id, access_token):
    """
    Function to post a tweet as a reply to a previously posted tweet.
    """
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "text": tweet_text,
        "reply": {
            "in_reply_to_tweet_id": in_reply_to_tweet_id
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 201:
        Logger.info("Reply tweet is post success!")
        Logger.info(f"Response: {response.json()}")
    else:
        Logger.info(f"Error when reply tweet: {response.status_code}")
        Logger.info(f"Details: {response.json()}")
    
    return response


def post_to_X(tweet_text:str, access_token:str) -> str:
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
    first_post_results = post_tweet(post, access_token)
    if first_post_results.status_code != 201:
        Logger.info("Error posting tweet: {}".format(first_post_results.text))
        return f"Post to Twitter failed with error: {first_post_results.text} and status code: {first_post_results.status_code}"
    
    id = first_post_results.json()["data"]["id"]
    Logger.info("Tweet posted with id: {}".format(id))
    if partTwo:
        rest_post_results = post_reply_tweet(partTwo, id, access_token)
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



# Create a tool for posting to twitter
post_X_tool = AgentTool(
    name="postx",
    description="Post the specific content to a X account.",
    properties = {
        "tweet_text": {
            "type": "string",
            "description": "The content of the tweet",
        },
        "access_token": {
            "type": "string",
            "description": "The access token of the X account",
        }
    },
    func=post_to_X,
    # enum_values={"units": ["celsius", "fahrenheit"]}
)
# Create a tool definition with name and description
Xtools:AgentTools = AgentTools(tools=[post_X_tool])
