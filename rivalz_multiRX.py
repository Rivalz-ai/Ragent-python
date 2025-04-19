# main_rx_system.py
import chainlit as cl
from rAgent.utils import Logger
import uuid
from rAgent.types import ConversationMessage
import os
from chainlit.user import PersistedUser, User
from backend.utils import generate_start_message, clean_text
from rAgent.agents import AgentResponse
import re
import asyncio
import requests
import aiohttp
import logging
# Other imports...
from chainlit.types import ThreadDict
# Check if file logging is already configured, if not, set it up
if not Logger.has_file_handler():  # You'll need to add this method to the Logger class
    log_file = Logger.setup_file_logging(log_level=logging.INFO)
    Logger.info(f"Logging set up to file: {log_file}")
else:
    Logger.info("File logging already configured")

from dotenv import load_dotenv
from rAgent.orchestrator import SwarmOrchestrator, OrchestratorConfig
from rAgent.storage import InMemoryChatStorage
from backend.agents import create_health_agent, create_travel_agent, create_rx_supervisor, create_default_agent,create_classifier   
load_dotenv()
Logger.info("Environment variables loaded")
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")
RIVALZ_URL = os.getenv("RIVAL_URL")
auth_key = os.getenv("auth_key")
# Flag để kiểm soát background task
polling_active = True


async def updating_task_stats(session_id:str, project_id: str):
    total = 0
    num_failed = 0
    num_done = 0
    async with aiohttp.ClientSession() as session:
        try:
            # Gọi API để lấy thống kê task
            Logger.info(f"Fetching task stats... for session: {session_id}")
            stat_url = RIVALZ_URL + f"/api/v2/agent/task/rx/stats?authen_key={project_id}&thread_id={session_id}"
            async with session.get(stat_url) as response:
                response_text = await response.text()
                Logger.info(f"Received task stats response: {response_text}")
                stats = await response.json()
                stats = stats["data"]
            # Tính toán giá trị progress
            value = int(stats["completion_percentage"])

            # Prepare list_failed (handle null case)
            list_failed = stats.get("list_failed", []) or []
            
            # Transform tweet IDs into full Twitter URLs
            completed_links = []
            for tweet_info in stats["list_result_done"]:
                if tweet_info["data"] is None:
                    tweet_info["data"] = "0"
                completed_links.append(f"https://twitter.com/i/web/status/{tweet_info['data']}")
            total = stats["total_tasks"]
            num_failed = stats["failed"]
            num_done = stats["done"]
            # Cập nhật sidebar với progress bar
            await cl.ElementSidebar.set_elements([
                cl.CustomElement(
                    name="CustomProgressBar", 
                    props={
                    "value": value,  
                    "title": "RX Post Tasks",                
                    "progressName": f"Posted {stats['done']}/{stats['total_tasks']}",
                    "details": {                            
                        "total": stats["total_tasks"],
                        "done": stats["done"],
                        "failed": stats["failed"], 
                        "pending": stats["pending"]
                    },
                    "completedLinks": completed_links,
                    "list_failed": list_failed  
                    }
                ),
            ])
        except Exception as e:
            Logger.error(f"Error updating task stats: {e}")
    return int(total) == int(num_done) + int(num_failed)

async def update_task_stats(session_id:str, project_id: str):
    """Background task để cập nhật thống kê task trên sidebar"""
    global polling_active
    while polling_active:
        try:
            # Gọi hàm cập nhật thống kê task
            done = await updating_task_stats(session_id, project_id)
            if done == True:
                Logger.info("All tasks done")
                break
            # Logger.info("Updated task stats")
        except Exception as e:
            Logger.error(f"Error in background task: {e}")
        await asyncio.sleep(5)

# Change to async function
async def start_orchestrator(project_id: str, shared_storage):
    # TODO: Implement the creation of the orchestrator
    # with the project_id
    Logger.info("Shared storage initialized")
    Logger.info("Creating agents...")
    custom_classifier = create_classifier()
    health_agent = create_health_agent()
    travel_agent = create_travel_agent()
    default_agent = create_default_agent()
    # Add await keyword to call the async function properly
    rx_supervisor = await create_rx_supervisor(storage = shared_storage, num_agents=9, project_id=project_id)
    # Initialize orchestrator
    Logger.info("Initializing orchestrator")
    orchestrator = SwarmOrchestrator(options=OrchestratorConfig(
            LOG_AGENT_CHAT=True,
            LOG_CLASSIFIER_CHAT=True,
            LOG_CLASSIFIER_RAW_OUTPUT=True,
            LOG_CLASSIFIER_OUTPUT=True,
            LOG_EXECUTION_TIMES=True,
            MAX_RETRIES=3,
            USE_DEFAULT_AGENT_IF_NONE_IDENTIFIED=True,
            MAX_MESSAGE_PAIRS_PER_AGENT=10
        ),
        classifier=custom_classifier,
        default_agent=default_agent,
        storage=shared_storage,
    )
    orchestrator.add_agent(rx_supervisor)
    orchestrator.add_agent(health_agent)
    orchestrator.add_agent(travel_agent)
    Logger.info(f"Creating orchestrator with project_id: {project_id}")
    return orchestrator, rx_supervisor


from chainlit import User
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs
import chainlit as cl

# User authentication callback
# @cl.password_auth_callback
# def auth_callback(project_name: str, project_id: str):
#     # Fetch the user matching username from your database
#     # and compare the hashed password with the value stored in the database
#     payload = {'project_id': project_id, 'project_name':project_name }
#     if project_name and project_id:
#         return cl.User(
#             identifier="project_name", metadata=payload
#         )
#     else:
#         return None

@cl.header_auth_callback
async def header_auth_callback(headers: Dict) -> Optional[User]:
    user = None
    referrer = headers.get('referer')
    print(f"Referrer: {referrer}")
    if referrer:
        parsed_url = urlparse(referrer)
        query_params = parse_qs(parsed_url.query)
        project_id = query_params.get('project_id', [None])[0]
        project_name = query_params.get('project_name', [None])[0]
        print(f"Project ID: {project_id}, Project Name: {project_name}")
        if project_id and project_name:
            payload = {'project_id': project_id, 'project_name':project_name }
            user = User(
                    identifier=project_name,
                    metadata=payload,
            )
            Logger.info(f"Authenticated user: {project_name} with project_id: {project_id}")
        else:
            Logger.warn("No project_id or project_name found in the URL")
            raise ValueError("No project_id or project_name found in the URL")
    return user
# @cl.password_auth_callback
# def auth_callback(project_name: str, project_id: str):
#     # Fetch the user matching username from your database
#     # and compare the hashed password with the value stored in the database
#     payload = {'project_id': project_id, 'project_name':project_name }
#     if project_name and project_id:
#         return cl.User(
#             identifier="project_name", metadata=payload
#         )
#     else:
#         return None
@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    cl.user_session.set("chat_history", [])
    
    for message in thread["steps"]:
        if message["type"] == "user_message":
            cl.user_session.get("chat_history").append({"role": "user", "content": message["output"]})
        elif message["type"] == "assistant_message":
            cl.user_session.get("chat_history").append({"role": "assistant", "content": message["output"]})
    
    user = cl.user_session.get("user")
    print(f"User: {user}")
    # Extract project info from user metadata
    project_id = None
    Logger.info(f"User is {user}")    
    if user and user.metadata:
        project_id = user.metadata.get("project_id")
        Logger.info(f"Project ID from user metadata: {project_id}")
    else:
        raise ValueError("User metadata is not available or does not contain project_id")
    # Log what we found
    if project_id:
        cl.user_session.set("project_id", project_id)
        Logger.info(f"Starting chat with project_id: {project_id}")
    else:
        await cl.Message(content="No project ID provided. Please select a project from the main page.").send()
        Logger.error("No project ID found in user session")
        return



    # Initialize orchestrator and rx_supervisor with project_id
    # Replace auth_key with project_id
    shared_storage = InMemoryChatStorage()
    orchestrator,rx_supervisor = await start_orchestrator(project_id,shared_storage)
    # Store the orchestrator and rx_supervisor in the user session
    cl.user_session.set("orchestrator", orchestrator)
    cl.user_session.set("rx_supervisor", rx_supervisor)
    cl.user_session.set("shared_storage", shared_storage)

    # Initialize sidebar with empty progress bar
    elements = [
        cl.CustomElement(
            name="CustomProgressBar", 
            props={
                "value": 0,  
                "title": "RX Post Tasks",                
                "progressName": "Posted 0/0",
                "details": {                            
                    "total": 0,
                    "done": 0,
                    "failed": 0, 
                    "pending": 0
                },
                "completedLinks": []  
            }
        ),
    ]
    await cl.ElementSidebar.set_elements(elements)
    await cl.ElementSidebar.set_title("Task Progress")
    Logger.info("Initialized sidebar with empty progress bar")

    global polling_active
    polling_active = True
    Logger.warn(f"continues with { thread['id']}")
    asyncio.create_task(update_task_stats(thread['id'], project_id))
    Logger.info("Started background task for updating task statistics")
    Logger.info(f"Chat resumed previous messages")




@cl.on_chat_start
async def start():
    # Get the project_id from the user session
    user = cl.user_session.get("user")
    print(f"User: {user}")
    # Extract project info from user metadata
    project_id = None
    Logger.info(f"User is {user}")    
    if user and user.metadata:
        project_id = user.metadata.get("project_id")
        Logger.info(f"Project ID from user metadata: {project_id}")
    else:
        raise ValueError("User metadata is not available or does not contain project_id")
    # Log what we found
    if project_id:
        cl.user_session.set("project_id", project_id)
        Logger.info(f"Starting chat with project_id: {project_id}")
    else:
        await cl.Message(content="No project ID provided. Please select a project from the main page.").send()
        Logger.error("No project ID found in user session")
        return

    Logger.info("New chat session starting")

    session_id = cl.user_session.get("id")
    Logger.info(f"session_id is {session_id}")
    if type(cl.user_session.get("user")) == PersistedUser:
        user_id = user.id
        Logger.info(f"User is {user_id}")
        cl.user_session.set("user_id", user_id)
    else:
        user_id = str(uuid.uuid4())
        cl.user_session.set("user_id", user_id)

    cl.user_session.set("chat_history", [])

    # Initialize orchestrator and rx_supervisor with project_id
    # Replace auth_key with project_id
    shared_storage = InMemoryChatStorage()
    orchestrator,rx_supervisor = await start_orchestrator(project_id,shared_storage)
    # Store the orchestrator and rx_supervisor in the user session
    cl.user_session.set("orchestrator", orchestrator)
    cl.user_session.set("rx_supervisor", rx_supervisor)
    cl.user_session.set("shared_storage", shared_storage)
    start_message = generate_start_message(orchestrator)
    # Add the start message to chat history
    await cl.Message(content=start_message).send()
    chat_history = cl.user_session.get("chat_history", [])
    chat_history.append({"role":"assistant","content": start_message})
    cl.user_session.set("chat_history", chat_history)
    

    # rx_supervisor.force_token_refresh()
    # Logger.info("Forced token refresh for RX Supervisor on session start")
    
    Logger.info("Chat session started successfully")

    # Initialize sidebar with empty progress bar
    elements = [
        cl.CustomElement(
            name="CustomProgressBar", 
            props={
                "value": 0,  
                "title": "RX Post Tasks",                
                "progressName": "Posted 0/0",
                "details": {                            
                    "total": 0,
                    "done": 0,
                    "failed": 0, 
                    "pending": 0
                },
                "completedLinks": []  
            }
        ),
    ]
    await cl.ElementSidebar.set_elements(elements)
    await cl.ElementSidebar.set_title("Task Progress")
    Logger.info("Initialized sidebar with empty progress bar")

    # global polling_active
    # polling_active = True
    # asyncio.create_task(updating_task_stats(session_id, project_id))
    # Logger.info("Started background task for updating task statistics")



@cl.on_message
async def main(message: cl.Message):
    thread_id = cl.context.session.thread_id
    print(f"Thread ID: {thread_id}")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("id")
    # thread_id = message.thread.id
    print(f"Session ID: {session_id}")

    
    project_id = cl.user_session.get("project_id")
    history = cl.user_session.get("chat_history", [])
    print(f"History: {history}")
    if len(history) > 0:
        team_info  =history[0].get("content", "No have team information")
    else:
        team_info = "No have team information"
    # Get the orchestrator for this specific session
    orchestrator = cl.user_session.get("orchestrator")
    if not orchestrator:
        await cl.Message(content="Session expired. Please refresh the page.").send()
        return

    Logger.info(f"Processing message for user: {user_id}, thread id: {thread_id}")
    Logger.debug(f"Message content: {message.content[:50]}...")

    msg = cl.Message(content="", author="My Assistant")
    await msg.send()  # Send the message immediately to start streaming
    cl.user_session.set("current_msg", msg)
    try:
        Logger.debug(f"Team info: {team_info}")
        response: AgentResponse = await orchestrator.route_request(message.content, user_id, thread_id, {"team_info": team_info})
        Logger.info(f"Received response from orchestrator for user: {user_id} is: {response.output.content[0].get('text', '')}")
        

        # Handle non-streaming responses
        if isinstance(response, AgentResponse) and response.streaming is False:
            raw_output = ""
            
            if isinstance(response.output, str):
                raw_output = response.output
            elif isinstance(response.output, ConversationMessage):
                raw_output = response.output.content[0].get('text', '')

            # Extract messages between <startagent> and <endagent>
            extracted_texts = re.findall(r'<\\?startagent>(.*?)<\\?endagent>', raw_output, re.DOTALL)
            
            # If nothing is extracted with the above pattern, try an alternative pattern
            if not extracted_texts:
                # Try alternative pattern with escaped backslashes and without space before endagent
                extracted_texts = re.findall(r'<\\startagent>(.*?)<\\endagent>', raw_output, re.DOTALL)
                
            # Log the extraction results
            Logger.info(f"Extraction result: {len(extracted_texts)} texts found")
            if extracted_texts:
                Logger.debug(f"First extracted text: {extracted_texts[0][:50]}...")

            if extracted_texts:  
                Logger.info(f"Found {len(extracted_texts)} agent message(s) to process")
                # ✅ Case 1: Found extracted messages → Send each one separately
                for i,extracted_text in enumerate(extracted_texts):
                    cleaned_text = clean_text(extracted_text)
                    if not cleaned_text:
                        continue
                    # Determine the author based on the content
                    author = "My Assistant"
                    if cleaned_text:
                        author = "X Assistant" if "[RX_Agent" in cleaned_text else "My Assistant"
                        if i ==0:
                            msg.author = author
                            await msg.stream_token(cleaned_text)
                            await msg.update()
                            
                        else:
                            sub_msg = cl.Message(content="", author=author)
                            await sub_msg.send()
                            await sub_msg.stream_token(cleaned_text) # Start streaming
                            await sub_msg.update() # Finalize this message # Finalize this message
            else:
                Logger.info("No agent messages found, sending full response")
                # ✅ Case 2: No extracted messages → Send full raw response
                author = "My Assistant"	
                cleaned_text = clean_text(raw_output)
                if "[RX_Agent" in cleaned_text:
                    author = "X Assistant"
                msg.author = author
                await msg.stream_token(cleaned_text)
                await msg.update() # Finalize the message
        asyncio.create_task(update_task_stats(thread_id, project_id))
    except Exception as e:
        Logger.error(f"Error processing message: {e}")
        await msg.stream_token("An error occurred while processing your request. Please try again later.")
        await msg.update()


# if __name__ == "__main__":
#     cl.run()
