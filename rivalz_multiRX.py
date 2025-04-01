# main_rx_system.py
import chainlit as cl
from rAgent.utils import Logger
from backend.router import orchestrator, rx_supervisor
import uuid
from rAgent.types import ConversationMessage
from backend.utils import generate_start_message, clean_text
from rAgent.agents import AgentResponse
import re
import asyncio
import requests
import aiohttp
import os
from rAgent.utils import Logger
import logging
# Other imports...

# Set up logging to both file and console
log_file = Logger.setup_file_logging(log_level=logging.INFO)

RIVALZ_URL = os.getenv("RIVAL_URL")
auth_key = os.getenv("auth_key")
# Flag để kiểm soát background task
polling_active = True

async def updating_task_stats(session_id:str):
    async with aiohttp.ClientSession() as session:
        try:
            # Gọi API để lấy thống kê task
            Logger.info(f"Fetching task stats... for session: {session_id}")
            stat_url = RIVALZ_URL + f"/agent/task/rx/stats?authen_key={auth_key}&thread_id={session_id}"
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

async def update_task_stats(session_id:str):
    """Background task để cập nhật thống kê task trên sidebar"""
    global polling_active
    while polling_active:
        try:
            # Gọi hàm cập nhật thống kê task
            await updating_task_stats(session_id)
            Logger.info("Updated task stats")
        except Exception as e:
            Logger.error(f"Error in background task: {e}")
        await asyncio.sleep(60)
    # async with aiohttp.ClientSession() as session:
    #     while polling_active:
    #         try:
    #             # Gọi API để lấy thống kê task
    #             Logger.info(f"Fetching task stats... for session: {session_id}")
    #             stat_url = RIVALZ_URL + f"/agent/task/rx/stats?authen_key={auth_key}&thread_id={session_id}"
    #             async with session.get(stat_url) as response:
    #                 response_text = await response.text()
    #                 Logger.info(f"Received task stats response: {response_text}")
    #                 stats = await response.json()
    #                 stats = stats["data"]
    #             # Tính toán giá trị progress
    #             value = int(stats["completion_percentage"])

    #             # Prepare list_failed (handle null case)
    #             list_failed = stats.get("list_failed", []) or []
                
    #             # Transform tweet IDs into full Twitter URLs
    #             completed_links = []
    #             for tweet_info in stats["list_result_done"]:
    #                 if tweet_info["data"] is None:
    #                     tweet_info["data"] = "0"
    #                 completed_links.append(f"https://twitter.com/i/web/status/{tweet_info['data']}")
                
    #             # Cập nhật sidebar với progress bar
    #             await cl.ElementSidebar.set_elements([
    #                 cl.CustomElement(
    #                     name="CustomProgressBar", 
    #                     props={
    #                     "value": value,  
    #                     "title": "RX Post Tasks",                
    #                     "progressName": f"Posted {stats['done']}/{stats['total_tasks']}",
    #                     "details": {                            
    #                         "total": stats["total_tasks"],
    #                         "done": stats["done"],
    #                         "failed": stats["failed"], 
    #                         "pending": stats["pending"]
    #                     },
    #                     "completedLinks": completed_links,
    #                     "list_failed": list_failed  
    #                     }
    #                 ),
    #                 ])
                
    #             # Chờ 5 giây trước khi cập nhật lại
    #             await asyncio.sleep(60)
    #             Logger.info("Updated task stats")
    #         except Exception as e:
    #             Logger.error(f"Error updating task stats: {e}")
    #             await asyncio.sleep(10)  # Chờ lâu hơn khi có lỗi




@cl.on_chat_start
async def start():
    Logger.info("New chat session starting")
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    Logger.info(f"Created user_id: {user_id}, session_id: {session_id}")
    cl.user_session.set("chat_history", [])

    # rx_supervisor.force_token_refresh()
    Logger.info("Forced token refresh for RX Supervisor on session start")
    start_message = generate_start_message(orchestrator)
    await cl.Message(content=start_message).send()
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

    global polling_active
    polling_active = True
    asyncio.create_task(update_task_stats(session_id))
    Logger.info("Started background task for updating task statistics")



@cl.on_message
async def main(message: cl.Message):
    user_id = cl.user_session.get("user_id")
    session_id = cl.user_session.get("session_id")
    Logger.info(f"Processing message for user: {user_id}, session: {session_id}")
    Logger.debug(f"Message content: {message.content[:50]}...")

    msg = cl.Message(content="", author="My Assistant")
    await msg.send()  # Send the message immediately to start streaming
    cl.user_session.set("current_msg", msg)
    try:
        response: AgentResponse = await orchestrator.route_request(message.content, user_id, session_id, {})
        Logger.info(f"Received response from orchestrator for user: {user_id}")
            

        # Handle non-streaming responses
        if isinstance(response, AgentResponse) and response.streaming is False:
            raw_output = ""
            
            if isinstance(response.output, str):
                raw_output = response.output
            elif isinstance(response.output, ConversationMessage):
                raw_output = response.output.content[0].get('text', '')

            # Extract messages between <\startagent> and <\endagent>
            extracted_texts = re.findall(r'<\\startagent>(.*?)<\\endagent>', raw_output, re.DOTALL)
            
            if extracted_texts:  
                Logger.info(f"Found {len(extracted_texts)} agent message(s) to process")
                # ✅ Case 1: Found extracted messages → Send each one separately
                for i,extracted_text in enumerate(extracted_texts):
                    cleaned_text = clean_text(extracted_text)
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
        asyncio.create_task(updating_task_stats(user_id))
    except Exception as e:
        Logger.error(f"Error processing message: {e}")
        await msg.stream_token("An error occurred while processing your request. Please try again later.")
        await msg.update()


if __name__ == "__main__":
    cl.run()