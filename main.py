# main_rx_system.py
import chainlit as cl
from rAgent.utils import Logger
from backend.router_normal import orchestrator, rx_supervisor
import uuid
from rAgent.types import ConversationMessage
from backend.utils import generate_start_message, clean_text
from rAgent.agents import AgentResponse
import re





@cl.on_chat_start
async def start():
    Logger.info("New chat session starting")
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    cl.user_session.set("user_id", user_id)
    cl.user_session.set("session_id", session_id)
    Logger.info(f"Created user_id: {user_id}, session_id: {session_id}")
    cl.user_session.set("chat_history", [])

    rx_supervisor.force_token_refresh()
    Logger.info("Forced token refresh for RX Supervisor on session start")

    
    start_message = generate_start_message(orchestrator)
    await cl.Message(content=start_message).send()
    Logger.info("Chat session started successfully")



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

    except Exception as e:
        Logger.error(f"Error processing message: {e}")
        await msg.stream_token("An error occurred while processing your request. Please try again later.")
        await msg.update()


if __name__ == "__main__":
    cl.run()