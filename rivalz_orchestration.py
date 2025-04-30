import uuid
import chainlit as cl
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import logging
from rAgent.utils import Logger
from rivalz_agent import RivalzAgent
from backend.utils import clean_text
from chainlit.user import PersistedUser, User
from rAgent.storage import InMemoryChatStorage
from rAgent.types import ConversationMessage
from rAgent.agents import AgentResponse
from chainlit import User
from typing import Dict, Optional
import re
from urllib.parse import urlparse, parse_qs
import chainlit as cl
import openapi_patch

# Set up logging
if not Logger.has_file_handler():
    log_file = Logger.setup_file_logging(log_level=logging.INFO)
    Logger.info(f"Logging set up to file: {log_file}")
else:
    Logger.info("File logging already configured")

# Load environment variables
load_dotenv()
RIVALZ_URL = os.getenv("RIVAL_URL", "https://staging-rome-api-v2.rivalz.ai")
PROJECT_ID = os.getenv("PROJECT_ID", "test_project")

polling_active = True










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











# --- Sidebar update logic ---
async def updating_task_stats(thread_id: str, project_id: str, agent_type: str):
    """
    Update task statistics in the sidebar for a given agent type
    
    Args:
        session_id (str): The session ID for the current chat
        project_id (str): The project authentication key
        agent_type (str): Type of agent (rc, rd, rx, etc.)
    """
    async with aiohttp.ClientSession() as session:
        try:
            # Call API to get task statistics
            Logger.info(f"Fetching {agent_type.upper()} task stats for session: {thread_id}")
            
            # Construct the API URL with authentication
            stat_url = f"{RIVALZ_URL}/api/v2/agent/task/{agent_type}/stats?authen_key={project_id}&thread_id={thread_id}"
            Logger.info(f"Requesting stats from URL: {stat_url}")
            
            async with session.get(stat_url) as response:
                response_text = await response.text()
                Logger.info(f"Received task stats response: {response_text[:200]}...")  # Log first 200 chars
                
                if response.status != 200:
                    Logger.error(f"Error fetching task stats: Status {response.status}, Response: {response_text}")
                    await update_empty_sidebar(f"Failed to fetch stats for {agent_type.upper()}", agent_type)
                    return True
                
                try:
                    stats = await response.json()
                    if not stats or "data" not in stats:
                        Logger.error(f"Invalid stats response format: {stats}")
                        await update_empty_sidebar("Invalid stats format", agent_type)
                        return True
                        
                    stats = stats["data"]
                except Exception as e:
                    Logger.error(f"Failed to parse JSON response: {e}")
                    await update_empty_sidebar(f"JSON parse error: {str(e)}", agent_type)
                    return True
            
            # Calculate progress value
            value = int(stats.get("completion_percentage", 0))
            
            # Prepare list_failed (handle null case)
            list_failed = stats.get("list_failed", []) or []
            
            # Process completed tasks based on agent type
            completed_tasks = []
            for task_info in stats.get("list_result_done", []):
                task_id = task_info.get("task_id", "Unknown")
                agent_id = task_info.get("id", "Unknown")
                data = task_info.get("data", "")
                
                # Handle different data formats based on agent type
                if agent_type.lower() == "rx":
                    # For RX agent, transform tweet IDs into Twitter URLs
                    if data is None:
                        data = "0"
                    completed_tasks.append(f"https://twitter.com/i/web/status/{data}")
                else:
                    # For other agents, create a detailed task object
                    data_summary = str(data)[:50] + "..." if len(str(data)) > 50 else str(data)
                    
                    task_obj = {
                        "id": task_id,
                        "data": data_summary,
                        "agent_id": agent_id,
                        "task_id": task_id
                    }
                    
                    
                    # Add num_loop for RD agent if available
                    if agent_type.lower() == "rd" and "num_loop" in task_info:
                        task_obj["num_loop"] = task_info.get("num_loop", 1)
                        
                    completed_tasks.append(task_obj)
            
            # Verify we have valid data to display before updating
            if completed_tasks:
                Logger.info(f"Found {len(completed_tasks)} completed tasks")
            else:
                Logger.warn("No completed tasks found")
            
            # Set title and progress name based on agent type
            title_map = {
                "rc": "RC System Tasks",
                "rd": "RD Data Tasks",
                "rx": "RX Post Tasks",
                "re": "RE Task"
            }
            
            progress_name_map = {
                "rc": f"Completed {stats['done']}/{stats['total_tasks']}",
                "rd": f"Completed {stats['done']}/{stats['total_tasks']}",
                "rx": f"Posted {stats['done']}/{stats['total_tasks']}",
                "re": f"Completed {stats['done']}/{stats['total_tasks']}"
            }
            total = stats["total_tasks"]
            num_failed = stats["failed"]
            num_done = stats["done"]
            
            title = title_map.get(agent_type.lower(), f"{agent_type.upper()} Tasks")
            progress_name = progress_name_map.get(agent_type.lower(), f"Completed {stats['done']}/{stats['total_tasks']}")
            
            # Build props object for CustomProgressBar
            progressbar_props = {
                "value": value,  
                "title": title,                
                "progressName": progress_name,
                "details": {                            
                    "total": stats.get("total_tasks", 0),
                    "done": stats.get("done", 0),
                    "failed": stats.get("failed", 0), 
                    "pending": stats.get("pending", 0)
                },
                "completedLinks": completed_tasks,
                "list_failed": list_failed  
            }
            
            # Log the exact props we're sending
            Logger.info(f"CustomProgressBar props: {progressbar_props}")
            
            # Update sidebar with new element
            try:
                await cl.ElementSidebar.set_elements([
                    cl.CustomElement(
                        name="CustomProgressBar", 
                        props=progressbar_props
                    ),
                ])
                Logger.info("Successfully updated sidebar with task stats")
                
            except Exception as e:
                Logger.error(f"Error setting sidebar elements: {str(e)}")
                return True
            return int(total) == (int(num_done) + int(num_failed))
        except Exception as e:
            Logger.error(f"Error updating task stats: {str(e)}")
            await update_empty_sidebar(f"Error: {str(e)}", agent_type)
            return True


async def update_empty_sidebar(error_message="No data available"):
    try:
        await cl.ElementSidebar.set_elements([
            cl.CustomElement(
                name="CustomProgressBar",
                props={
                    "value": 0,
                    "title": "System Tasks",
                    "progressName": error_message,
                    "details": {
                        "total": 0,
                        "done": 0,
                        "failed": 0,
                        "pending": 0
                    },
                    "completedLinks": [],
                    "list_failed": []
                }
            ),
        ])
        Logger.info(f"Updated sidebar with empty progress bar: {error_message}")
    except Exception as e:
        Logger.error(f"Failed to update empty sidebar: {str(e)}")

async def update_task_stats(session_id: str, project_id: str, agent_type: str):
    while True:
        try:
            Logger.info(f"Updating {agent_type.upper()} task stats...")
            done = await updating_task_stats(session_id, project_id, agent_type)
            if done == True:
                Logger.info("All tasks done")
                break
        except Exception as e:
            Logger.error(f"Error in background task: {str(e)}")
        await asyncio.sleep(5)

@cl.set_chat_profiles
async def chat_profiles():
    profiles =  [
        cl.ChatProfile(
            name="RX",
            markdown_description="A social media agent for posting tweets.",
            icon="https://rome.rivalz.ai/icons/rx.svg",
            default=True
        ),
        cl.ChatProfile(
            name="RC",
            markdown_description="A compute resource agent for system monitoring.",
            icon="https://rome.rivalz.ai/icons/rc.svg"
        ),
        cl.ChatProfile(
            name="RD",
            markdown_description="A data resource agent for data fetching and processing.",
            icon="https://rome.rivalz.ai/icons/rd.svg"
        ),
        cl.ChatProfile(
            name="RE",
            markdown_description="A resource execute agent for specific tasks.",
            icon="https://rome.rivalz.ai/icons/re.svg"
        )
    ]
    Logger.info(f"Registering chat profiles: {profiles}")
    return profiles

@cl.on_chat_start
async def start():
    # Get the project_id from the user session
    user = cl.user_session.get("user")
    project_id = None
    if user and user.metadata:
        project_id = user.metadata.get("project_id")
        Logger.info(f"Project ID from user metadata: {project_id}")
    else:
        raise ValueError("User metadata is not available or does not contain project_id")

    # Initialize the agent asynchronously using the create factory method
    shared_storage = InMemoryChatStorage()
    rival_agents = await RivalzAgent.create(project_id, shared_storage)
    cl.user_session.set("rivalz_agents", rival_agents)
    
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


    # Get selected profile
    profile = cl.user_session.get("chat_profile")
    if not profile:
        Logger.error("No chat profile selected")
        await cl.Message(content="Error: No agent profile selected").send()
        return
     # Extract agent type from profile name (rx, rc, rd, re)
    agent_type = profile.lower()

    # Initialize orchestrator and rx_supervisor with project_id
    shared_storage = InMemoryChatStorage()
    rival_agents = await RivalzAgent.create(project_id, shared_storage)
    cl.user_session.set("rivalz_agents", rival_agents)
    cl.user_session.set("shared_storage", shared_storage)
    start_message = rival_agents.generate_start_message()
    # Add the start message to chat history
    await cl.Message(content=start_message).send()
    chat_history = cl.user_session.get("chat_history", [])
    chat_history.append({"role":"assistant","content": start_message})
    cl.user_session.set("chat_history", chat_history)
    
    Logger.info("Chat session started successfully")

    # Initialize sidebar with empty progress bar
    await update_empty_sidebar(f"{agent_type.upper()} Agent")
    await cl.ElementSidebar.set_title("Task Progress")
    Logger.info("Initialized sidebar with empty progress bar")
    welcome_messages = {
            "rx": "Welcome to RX Social Agent! How can I help you with your social media tasks?",
            "rc": "RC Compute Agent ready! What system operations can I help you with?",
            "rd": "RD Data Agent at your service! What data processing tasks do you need?",
            "re": "RE Execution Agent initialized! What tasks should we execute?"
        }
    await cl.Message(content=welcome_messages.get(agent_type, "Agent initialized and ready!")).send() 



@cl.on_message
async def main(message: cl.Message):
    thread_id = cl.context.session.thread_id
    print(f"Thread ID: {thread_id}")
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("id")
    print(f"Session ID: {session_id}")

    
    project_id = cl.user_session.get("project_id")
    history = cl.user_session.get("chat_history", [])
    print(f"History: {history}")
    _history = [ConversationMessage(role=msg["role"], content=[{'text':msg["content"]}]) for msg in history]
    if len(history) > 0:
        team_info  =history[0].get("content", "No have team information")
    else:
        team_info = "No have team information"


    # Get selected profile
    profile = cl.user_session.get("chat_profile")
    if not profile:
        Logger.error("No chat profile selected")
        await cl.Message(content="Error: No agent profile selected").send()
        return
    
     # Extract agent type from profile name (rx, rc, rd, re)
    agent_type = profile.lower()  
    # Get the orchestrator for this specific session
    rivalz_agents: RivalzAgent = cl.user_session.get("rivalz_agents")

    

    Logger.info(f"Processing message for user: {user_id}, thread id: {thread_id}")
    Logger.debug(f"Message content: {message.content[:50]}...")

    msg = cl.Message(content="", author="My Assistant")
    await msg.send()  # Send the message immediately to start streaming
    cl.user_session.set("current_msg", msg)
    try:
        Logger.info(f"Team info: {team_info}")
        response = await rivalz_agents.process_request(message.content, user_id, thread_id,_history, {"team_info": team_info}, agent_type)
        Logger.info(f"Received response from orchestrator for user: {user_id} is: {response.output.content[0].get('text', '')}")
        
        # Get selected profile/agent type
        profile = cl.user_session.get("chat_profile")
        if not profile:
            Logger.error("No chat profile selected")
            return
            
        # Extract agent type from profile name
        agent_type = profile.lower()
        print(f"update task stats Agent type: {agent_type}, projectid = {project_id}, threadid = {thread_id}")
        # Start background task for updating task stats
        asyncio.create_task(update_task_stats(thread_id, project_id, agent_type))

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
                        if "[RX_Agent" in cleaned_text:
                            author = "RX Assistant"
                        elif "[RC_Agent" in cleaned_text:
                            author = "RC Assistant"
                        elif "[RD_Agent" in cleaned_text:
                            author = "RD Assistant"
                        elif "[RE_Agent" in cleaned_text:
                            author = "RE Assistant"
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
    except Exception as e:
        Logger.error(f"Error processing message: {e}")
        await msg.stream_token("An error occurred while processing your request. Please try again later.")
        await msg.update()
@cl.on_chat_end
async def end():
    global polling_active
    polling_active = False
    Logger.info("Chat ended, stopping background task")

# Run Chainlit server
# if __name__ == "__main__":
#     cl.run()
