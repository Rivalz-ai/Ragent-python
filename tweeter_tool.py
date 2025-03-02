# Function for splitting up posts that are too long for twitter.
from multi_agent_orchestrator.utils import Logger
from tools import AgentTools, AgentTool
import requests
def split_post(text):
    Logger.info("Splitting post that is too long for twitter.")
    first = text
    second = "" # to initialize
    # We first try to split the post by paragraphs, and send as many as can fit in the first post,
    # and the rest in the second.
    if "\n" in text:
        paragraphs = text.split("\n")
        i = 1
        while len(first) > 280 and i < len(paragraphs):
            first = "\n".join(paragraphs[:(len(paragraphs) - i)]) + "\n"
            second = "\n".join(paragraphs[(len(paragraphs) - i):])
            i += 1
    # If post can't be split by paragraph, we try by sentence.
    if len(first) > 280:
        first = text
        sentences = text.split(". ")
        i = 1
        while len(first) > 280 and i < len(sentences):
            first = ". ".join(sentences[:(len(sentences) - i)]) + "."
            second = ". ".join(sentences[(len(sentences) - i):])
            i += 1
    # If splitting by sentence does not result in a short enough post, we try splitting by words instead.
    if len(first) > 280:
        first = text
        words = text.split(" ")
        i = 1
        while len(first) > 280 and i < len(words):
            first = " ".join(words[:(len(words) - i)])
            second = " ".join(words[(len(words) - i):])
            i += 1
    # If splitting has ended up with either a first or second part that is too long, we return empty
    # strings and the post is not sent to twitter.
    if len(first) > 280 or len(second) > 280:
        Logger.info("Was not able to split post.", "error")
        first = ""
        second = ""
    return first, second


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
