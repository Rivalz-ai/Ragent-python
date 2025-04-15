import uuid
import chainlit as cl
import os
from dotenv import load_dotenv
import asyncio
import aiohttp
import json
import logging
from datetime import datetime

# Import RDAgent for Data Resource operations
from rAgent.ragents import RDAgent, RDAgentOptions
from rAgent.types import ConversationMessage
from rAgent.agents import AgentCallbacks
from rAgent.utils import Logger

# Set up logging
log_file = Logger.setup_file_logging(log_level=logging.INFO)

# Flag to control background task
polling_active = True

class ChainlitAgentCallbacks(AgentCallbacks):
    def on_llm_new_token(self, token: str) -> None:
        asyncio.run(cl.user_session.get("current_msg").stream_token(token))

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
DEEP_INFRA_KEY = os.getenv("deep_infra_api_key")
DEEP_INFRA_URL = os.getenv("base_url")
DEEP_INFRA_MODEL= os.getenv("deep_infra_model")
PROJECT_AUTH_TOKEN = os.getenv("auth_key", "test_token")
PROJECT_ID = os.getenv("PROJECT_ID", "test_project")
RIVALZ_URL = os.getenv("RIVAL_URL", "https://staging-rome-api-v2.rivalz.ai/agent")

async def updating_task_stats(session_id: str, project_id: str):
    """Update task statistics in the sidebar"""
    async with aiohttp.ClientSession() as session:
        try:
            # Call API to get task statistics
            Logger.info(f"Fetching RD task stats for session: {session_id}")
            # Uses the rd endpoint instead of rc
            stat_url = f"{RIVALZ_URL}/agent/task/rd/stats?authen_key={project_id}&thread_id={session_id}"
            
            Logger.info(f"Requesting stats from URL: {stat_url}")
            
            async with session.get(stat_url) as response:
                response_text = await response.text()
                Logger.info(f"Received task stats response: {response_text[:200]}...")  # Log first 200 chars
                
                if response.status != 200:
                    Logger.error(f"Error fetching task stats: Status {response.status}, Response: {response_text}")
                    # Even if we can't get stats, still update the sidebar with at least empty data
                    await update_empty_sidebar("Failed to fetch stats")
                    return
                
                try:
                    stats = await response.json()
                    if not stats or "data" not in stats:
                        Logger.error(f"Invalid stats response format: {stats}")
                        await update_empty_sidebar("Invalid stats format")
                        return
                        
                    stats = stats["data"]
                except Exception as e:
                    Logger.error(f"Failed to parse JSON response: {e}")
                    await update_empty_sidebar(f"JSON parse error: {str(e)}")
                    return
                
            # Calculate progress value
            value = int(stats["completion_percentage"])
            
            # Prepare list_failed (handle null case)
            list_failed = stats.get("list_failed", []) or []
            
            # Prepare completed tasks list with formatted data details
            completed_tasks = []
            for task_info in stats.get("list_result_done", []):
                task_data = task_info.get("data", {})
                task_id = task_info.get("task_id", "Unknown")
                agent_id = task_info.get("id", "Unknown")
                
                # Format data based on what we retrieved
                if isinstance(task_data, dict):
                    # For URL data or structured data
                    if "url" in task_data:
                        data_summary = f"URL: {task_data['url']}"
                        if "status" in task_data:
                            data_summary += f" | Status: {task_data['status']}"
                        if "content_length" in task_data:
                            data_summary += f" | Size: {task_data['content_length']}"
                    else:
                        # Generic handling for any structured data
                        data_summary = json.dumps(task_data, sort_keys=True, indent=2)
                elif isinstance(task_data, str):
                    # For string data
                    data_summary = task_data
                else:
                    # Fallback
                    data_summary = "Data fetched successfully"
                
                completed_tasks.append({
                    "id": task_id,
                    "data": data_summary,
                    "agent_id": agent_id,
                    "task_id": task_id
                })
            
            # Verify we have valid data to display before updating
            if completed_tasks:
                Logger.info(f"Found {len(completed_tasks)} completed tasks")
            else:
                Logger.warn("No completed tasks found")
            
            # Build props object for CustomProgressBar
            progressbar_props = {
                "value": value,  
                "title": "RD Data Tasks",                
                "progressName": f"Completed {stats['done']}/{stats['total_tasks']}",
                "details": {                            
                    "total": stats["total_tasks"],
                    "done": stats["done"],
                    "failed": stats["failed"], 
                    "pending": stats["pending"]
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
            await update_empty_sidebar(f"Error: {str(e)}")

async def update_empty_sidebar(error_message="No data available"):
    """Update sidebar with empty progress bar when there's an error"""
    try:
        await cl.ElementSidebar.set_elements([
            cl.CustomElement(
                name="CustomProgressBar", 
                props={
                    "value": 0,  
                    "title": "RD Data Tasks",                
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

async def update_task_stats(session_id: str, project_id: str):
    """Background task to update task statistics on the sidebar"""
    global polling_active
    while polling_active:
        try:
            # Call function to update task statistics
            await updating_task_stats(session_id, project_id)
            Logger.info("Updated RD task stats")
        except Exception as e:
            Logger.error(f"Error in background task: {str(e)}")
        await asyncio.sleep(10)  # Update every 10 seconds

# Create RDAgent
def create_rd_agent():
    return RDAgent(RDAgentOptions(
        name="RD_Agent",
        description=(
            "Data Resource Agent specialized in data fetching, monitoring, and processing. "
            "Can perform URL checks, periodic data retrieval, file operations, and data transformations. "
            "Handles data resources like APIs, files, and databases efficiently."
        ),
        api_key=OPENAI_API_KEY,
        model=OPENAI_MODEL,
        project_auth_token=PROJECT_AUTH_TOKEN,
        project_id=PROJECT_ID,
        api_base_url=RIVALZ_URL,
        inference_config={
            'maxTokens': 500,
            'temperature': 0.5,
            'topP': 0.8,
            'stopSequences': []
        },
        callbacks=ChainlitAgentCallbacks(),
    ))

agent = create_rd_agent()

async def hit_url(session_id: str, url: str, interval: int = 60):
    """Schedule periodic URL hits"""
    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                "type": 0,
                "interval": interval,
                "session_id": session_id,
                "data": {
                    "url": url
                }
            }
            
            # Log the request payload
            Logger.info(f"Scheduling URL hit with payload: {payload}")
            
            # Send the request to the API
            hit_url_endpoint = f"{RIVALZ_URL}/agent/task/rd/schedule?authen_key={PROJECT_AUTH_TOKEN}"
            async with session.post(hit_url_endpoint, json=payload) as response:
                response_text = await response.text()
                Logger.info(f"Hit URL response: {response_text}")
                
                if response.status != 200:
                    return f"Error scheduling URL hit: Status {response.status}, Response: {response_text}"
                
                response_data = await response.json()
                return f"Successfully scheduled URL hit. Job ID: {response_data.get('data', {}).get('job_id', 'Unknown')}"
                
        except Exception as e:
            Logger.error(f"Error hitting URL: {str(e)}")
            return f"Error hitting URL: {str(e)}"

@cl.on_chat_start
async def start():
    # Generate unique IDs for this session
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    
    # Store session information
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("project_id", PROJECT_ID)
    cl.user_session.set("chat_history", [])
    
    # Set agent's session ID
    agent.set_session_id(session_id)

    # Initialize sidebar with empty progress bar
    initial_props = {
        "value": 0,  
        "title": "RD Data Tasks",                
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
    
    Logger.info(f"Initializing sidebar with props: {initial_props}")
    
    try:
        elements = [
            cl.CustomElement(
                name="CustomProgressBar", 
                props=initial_props
            ),
        ]
        await cl.ElementSidebar.set_elements(elements)
        await cl.ElementSidebar.set_title("RD Task Progress")
        Logger.info("Initialized sidebar with empty progress bar")
    except Exception as e:
        Logger.error(f"Error initializing sidebar: {str(e)}")
    
    # Start background task for updating task statistics
    global polling_active
    polling_active = True
    asyncio.create_task(update_task_stats(session_id, PROJECT_ID))
    
    # Send welcome message
    await cl.Message(
        content="👋 Welcome! I'm your Data Resource Agent. I can help with data fetching, monitoring URLs, processing data files, and executing data-related tasks. How can I assist you today?"
    ).send()

    # Add action buttons for common data tasks
    actions = [
        cl.Action(name="hit_url", value="hit_url", description="Schedule a URL to be checked periodically"),
        cl.Action(name="data_transform", value="data_transform", description="Transform data formats (JSON, CSV, etc.)"),
        cl.Action(name="file_operations", value="file_operations", description="Perform operations on data files"),
        cl.Action(name="data_extraction", value="data_extraction", description="Extract specific data from sources")
    ]
    await cl.Message(content="You can use these common data operations:", actions=actions).send()

@cl.on_action
async def on_action(action: cl.Action):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")

    if action.name == "hit_url":
        # Create input form for URL hitting
        elements = [
            cl.Input(id="url", label="URL to monitor", placeholder="https://example.com"),
            cl.Input(id="interval", label="Check interval (seconds)", placeholder="60", input_type="number")
        ]
        await cl.Message(content="Please provide the URL details:", elements=elements).send()
    
    elif action.name == "data_transform":
        await cl.Message(content="What type of data would you like to transform? Please describe the input format and desired output format.").send()
    
    elif action.name == "file_operations":
        await cl.Message(content="What operations would you like to perform on your data files? I can help with parsing, filtering, or organizing data files.").send()
    
    elif action.name == "data_extraction":
        await cl.Message(content="What data would you like to extract? Please describe the source and the specific information you're looking for.").send()

@cl.on_form_submit
async def on_form_submit(form: cl.Form):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    
    # Handle URL hitting form
    if "url" in form.data:
        url = form.data.get("url")
        interval_str = form.data.get("interval", "60")
        try:
            interval = int(interval_str)
        except ValueError:
            interval = 60
            
        # Schedule the URL hit
        result = await hit_url(session_id, url, interval)
        
        # Send response
        await cl.Message(content=f"⏱️ {result}\nI'll monitor the URL: {url} every {interval} seconds and report the results.").send()
        
        # Force an immediate update of the task stats
        project_id = cl.user_session.get("project_id")
        asyncio.create_task(updating_task_stats(session_id, project_id))

@cl.on_message
async def handle_message(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    project_id = cl.user_session.get("project_id")

    # Check for bash command requests
    if message.content.startswith("bash:") or message.content.startswith("$"):
        cmd = message.content.replace("bash:", "").replace("$", "", 1).strip()
        
        # Process bash command for data operations
        msg = cl.Message(content=f"Processing data command: `{cmd}`")
        await msg.send()
        
        # Here you would implement secure command execution for data tasks
        # For demonstration, we're just simulating the response
        
        if "curl" in cmd or "wget" in cmd:
            # Simulate fetching data from URL
            await msg.stream_token("\n\nFetching data from URL...\n")
            await asyncio.sleep(1)
            await msg.stream_token("Data fetched successfully! Would you like me to process this data further?")
            
        elif "grep" in cmd or "awk" in cmd or "sed" in cmd:
            # Simulate data filtering
            await msg.stream_token("\n\nFiltering data...\n")
            await asyncio.sleep(1)
            await msg.stream_token("Data filtered successfully! Here's a sample of the output:\n```\n[Sample filtered data would appear here]\n```")
            
        elif "jq" in cmd:
            # Simulate JSON processing
            await msg.stream_token("\n\nProcessing JSON data...\n")
            await asyncio.sleep(1)
            await msg.stream_token("JSON processed successfully! Here's the transformed data:\n```json\n{\n  \"sample\": \"data\"\n}\n```")
            
        else:
            # General command response
            await msg.stream_token("\n\nProcessing command...\n")
            await asyncio.sleep(1)
            await msg.stream_token("Command execution finished. Would you like to schedule this as a recurring data task?")
        
        await msg.update()
    else:
        # Handle regular message with the agent
        msg = cl.Message(content="")
        await msg.send()
        cl.user_session.set("current_msg", msg)

        response = await agent.process_request(
            input_text=message.content,
            user_id=user_id,
            session_id=session_id,
            chat_history=[]
        )

        if isinstance(response, ConversationMessage):
            await msg.stream_token(response.content[0]["text"])

        await msg.update()
    
    # Update task statistics after each message
    asyncio.create_task(updating_task_stats(session_id, project_id))

@cl.on_chat_end
async def end():
    # Stop the background task when chat ends
    global polling_active
    polling_active = False
    Logger.info("Chat ended, stopping background task")

# Run Chainlit server
if __name__ == "__main__":
    cl.run()