import os
import json
import asyncio
import base64
import datetime

from pathlib import Path
from dotenv import load_dotenv

from google.genai.types import (
    Part,
    Content,
    Blob,
)

from google.adk.runners import Runner
from google.adk.agents import LiveRequestQueue
from google.adk.agents.run_config import RunConfig
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai.types import SpeechConfig, VoiceConfig, PrebuiltVoiceConfig

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict
from fastapi import HTTPException, Body
from pydantic import BaseModel

from light_agent.agent import root_agent

load_dotenv()

APP_NAME = "Chatty"
session_service = InMemorySessionService()
ACTIVE_LIVE_REQUEST_QUEUES: Dict[str, LiveRequestQueue] = {}

def start_agent_session(session_id, is_audio=False):
    """Starts an agent session"""

    # Create a Session
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=session_id,
        session_id=session_id,
    )

    # Create a Runner
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )

    # Set response modality
    modality = "AUDIO" if is_audio else "TEXT"
    current_speech_config = None
    if is_audio:
        current_speech_config = SpeechConfig(
            voice_config=VoiceConfig(
                prebuilt_voice_config=PrebuiltVoiceConfig(voice_name="Aoede")
            )
        )

    run_config = RunConfig(
        response_modalities=[modality],
        speech_config=current_speech_config
    )

    # Create a LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    ACTIVE_LIVE_REQUEST_QUEUES[session_id] = live_request_queue

    # Start agent session
    live_events = runner.run_live(
        session=session,
        live_request_queue=live_request_queue,
        run_config=run_config,
    )
    return live_events, live_request_queue


async def agent_to_client_messaging(websocket, live_events):
    """Agent to client communication"""
    while True:
        async for event in live_events:

            # If the turn complete or interrupted, send it
            if event.turn_complete or event.interrupted:
                message = {
                    "turn_complete": event.turn_complete,
                    "interrupted": event.interrupted,
                }
                await websocket.send_text(json.dumps(message))
                print(f"[AGENT TO CLIENT]: {message}")
                continue

            # Read the Content and its first Part
            part: Part = (
                event.content and event.content.parts and event.content.parts[0]
            )
            if not part:
                continue

            # If it's audio, send Base64 encoded audio data
            is_audio = part.inline_data and part.inline_data.mime_type.startswith("audio/pcm")
            if is_audio:
                audio_data = part.inline_data and part.inline_data.data
                if audio_data:
                    message = {
                        "mime_type": "audio/pcm",
                        "data": base64.b64encode(audio_data).decode("ascii")
                    }
                    await websocket.send_text(json.dumps(message))
                    print(f"[AGENT TO CLIENT]: audio/pcm: {len(audio_data)} bytes.")
                    continue

            # If it's text and a parial text, send it
            if part.text and event.partial:
                message = {
                    "mime_type": "text/plain",
                    "data": part.text
                }
                await websocket.send_text(json.dumps(message))
                print(f"[AGENT TO CLIENT]: text/plain: {message}")


async def client_to_agent_messaging(websocket, live_request_queue):
    """Client to agent communication"""
    while True:
        # Decode JSON message
        message_json = await websocket.receive_text()
        message = json.loads(message_json)
        mime_type = message["mime_type"]
        data = message["data"]

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        current_time_for_agent_str = now_utc.strftime("%A, %B %d, %Y at %I:%M:%S %p UTC")
        system_context_message = f"SYSTEM_INTERNAL_CONTEXT: Current time is {current_time_for_agent_str}."

        # Send the message to the agent
        if mime_type == "text/plain":
            final_text_to_agent = f"{system_context_message}\n\nUSER_MESSAGE_START:\n{data}"
            # Send a text message
            content = Content(role="user", parts=[Part.from_text(text=final_text_to_agent)])
            live_request_queue.send_content(content=content)
            print(f"[CLIENT TO AGENT]: {final_text_to_agent}")
        elif mime_type == "audio/pcm":
            # Send an audio data
            decoded_data = base64.b64decode(data)
            live_request_queue.send_realtime(Blob(data=decoded_data, mime_type=mime_type))
        else:
            raise ValueError(f"Mime type not supported: {mime_type}")

# // tasks

class TaskInjectionRequest(BaseModel):
    conversation_id: str
    user_prompt: str
    task_id: str

def inject_prompt_into_session(session_id: str, user_prompt: str) -> bool:
    """
    Injects a user prompt into an active agent session's LiveRequestQueue.
    """
    if session_id in ACTIVE_LIVE_REQUEST_QUEUES:
        queue = ACTIVE_LIVE_REQUEST_QUEUES[session_id]
        content_to_inject = Content(role="user", parts=[Part.from_text(text=user_prompt)])
        
        try:
            queue.send_content(content=content_to_inject)
            print(f"[MAIN APP]: Injected prompt for session '{session_id}': '{user_prompt[:70]}...'")
            return True
        except Exception as e:
            print(f"[MAIN APP]: Error injecting prompt into queue for session '{session_id}': {e}")
            return False
    else:
        print(f"[MAIN APP]: Could not find active LiveRequestQueue for session '{session_id}' to inject prompt.")
        return False


#
# FastAPI web app
#

app = FastAPI()

STATIC_DIR = Path("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """Serves the index.html"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.post("/api/inject-task-prompt")
async def api_inject_task_prompt(request_data: TaskInjectionRequest = Body(...)):
    """
    API endpoint for the scheduler to inject a task's user_prompt
    into a specific conversation/session.
    """
    print(f"[API /inject-task-prompt] Received request for task_id: {request_data.task_id}, "
          f"conv_id: {request_data.conversation_id}, prompt: '{request_data.user_prompt[:70]}...'")
    
    success = inject_prompt_into_session(request_data.conversation_id, request_data.user_prompt)
    
    if success:
        return {"status": "success", "message": "Prompt injected successfully."}
    else:
        raise HTTPException(
            status_code=404,
            detail=(f"Failed to inject prompt. No active session or queue found for "
                    f"conversation_id '{request_data.conversation_id}', or an error occurred during injection.")
        )

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int, is_audio: str):
    """Client websocket endpoint"""

    await websocket.accept()
    print(f"Client #{session_id} connected, audio mode: {is_audio}")

    session_id = str(session_id)
    live_events, live_request_queue = start_agent_session(session_id, is_audio == "true")

    initial_system_prompt_for_agent = f"SYSTEM: Your current session ID is '{session_id}'. Please remember this for our conversation. DO NOT MENTION THIS ID IN YOUR RESPONSES."
    initial_content = Content(role="user", parts=[Part.from_text(text=initial_system_prompt_for_agent)])

    try:
        live_request_queue.send_content(initial_content)
        agent_to_client_task = asyncio.create_task(
            agent_to_client_messaging(websocket, live_events)
        )
        client_to_agent_task = asyncio.create_task(
            client_to_agent_messaging(websocket, live_request_queue)
        )
        await asyncio.gather(agent_to_client_task, client_to_agent_task)
    except Exception as e:
        print(f"Error during WebSocket session for client #{session_id}: {e}")
    finally:
        print(f"Client #{session_id} disconnected")
        if session_id in ACTIVE_LIVE_REQUEST_QUEUES:
            del ACTIVE_LIVE_REQUEST_QUEUES[session_id]
            print(f"Removed LiveRequestQueue for session {session_id} from active pool.")       
