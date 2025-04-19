import uuid
import chainlit as cl
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import logging
from rAgent.utils import Logger
from rivalz_agent import RivalzAgent
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


# --- Sidebar update logic ---
async def updating_task_stats(session_id: str, project_id: str, agent_type: str):
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
            Logger.info(f"Fetching {agent_type.upper()} task stats for session: {session_id}")
            
            # Construct the API URL with authentication
            stat_url = f"{RIVALZ_URL}/api/v2/agent/task/{agent_type}/stats?authen_key={project_id}&thread_id={session_id}"
            Logger.info(f"Requesting stats from URL: {stat_url}")
            
            async with session.get(stat_url) as response:
                response_text = await response.text()
                Logger.info(f"Received task stats response: {response_text[:200]}...")  # Log first 200 chars
                
                if response.status != 200:
                    Logger.error(f"Error fetching task stats: Status {response.status}, Response: {response_text}")
                    await update_empty_sidebar(f"Failed to fetch stats for {agent_type.upper()}", agent_type)
                    return
                
                try:
                    stats = await response.json()
                    if not stats or "data" not in stats:
                        Logger.error(f"Invalid stats response format: {stats}")
                        await update_empty_sidebar("Invalid stats format", agent_type)
                        return
                        
                    stats = stats["data"]
                except Exception as e:
                    Logger.error(f"Failed to parse JSON response: {e}")
                    await update_empty_sidebar(f"JSON parse error: {str(e)}", agent_type)
                    return
            
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
                "rx": "RX Post Tasks"
            }
            
            progress_name_map = {
                "rc": f"Completed {stats['done']}/{stats['total_tasks']}",
                "rd": f"Completed {stats['done']}/{stats['total_tasks']}",
                "rx": f"Posted {stats['done']}/{stats['total_tasks']}"
            }
            
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
        except Exception as e:
            Logger.error(f"Error updating task stats: {str(e)}")
            await update_empty_sidebar(f"Error: {str(e)}", agent_type)


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
    global polling_active
    while polling_active:
        try:
            await updating_task_stats(session_id, project_id, agent_type)
            Logger.info(f"Updated {agent_type.upper()} task stats")
        except Exception as e:
            Logger.error(f"Error in background task: {str(e)}")
        await asyncio.sleep(10)

@cl.set_chat_profiles
async def chat_profiles():
    return [
        cl.ChatProfile(
            name="Rivalz Agent",
            description="A simulated agent for task management.",
            icon="🤖",
            default=True
        ),
        cl.ChatProfile(
            name="Custom Agent",
            description="A custom agent for specific tasks.",
            icon="🛠️"
        )
    ]

@cl.on_chat_start
async def start():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("project_id", PROJECT_ID)
    cl.user_session.set("chat_history", [])

    initial_props = {
        "value": 0,
        "title": f"{agent_type.upper()} System Tasks",
        "progressName": "Completed 0/0",
        "details": {
            "total": 0,
            "done": 0,
            "failed": 0,
            "pending": 0
        },
        "completedLinks": [],
        "list_failed": []
    }
    try:
        elements = [
            cl.CustomElement(
                name="CustomProgressBar",
                props=initial_props
            ),
        ]
        await cl.ElementSidebar.set_elements(elements)
        await cl.ElementSidebar.set_title(f"{agent_type.upper()} Task Progress")
        Logger.info("Initialized sidebar with empty progress bar")
    except Exception as e:
        Logger.error(f"Error initializing sidebar: {str(e)}")
    global polling_active
    polling_active = True
    asyncio.create_task(update_task_stats(session_id, PROJECT_ID, agent_type))
    await cl.Message(
        content=f"👋 Welcome! I'm your {agent_type.upper()} Agent. How can I assist you today?"
    ).send()

@cl.on_message
async def handle_message(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    project_id = cl.user_session.get("project_id")
    agent_type = cl.user_session.get("agent_type")
    msg = cl.Message(content="")
    await msg.send()
    cl.user_session.set("current_msg", msg)
    # Here you would call the appropriate RivalzAgent logic
    await msg.stream_token(f"[Simulated {agent_type.upper()} Agent Response]: {message.content}")
    await msg.update()
    asyncio.create_task(updating_task_stats(session_id, project_id, agent_type))

@cl.on_chat_end
async def end():
    global polling_active
    polling_active = False
    Logger.info("Chat ended, stopping background task")

# Run Chainlit server
if __name__ == "__main__":
    cl.run()
