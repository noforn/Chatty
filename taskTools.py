import asyncio
import json
import os
import uuid
from typing import Optional, List, Dict, Any

SCHEDULED_TASKS_FILE = "scheduled_tasks.json"

def _load_tasks() -> List[Dict[str, Any]]:
    """
    Loads scheduled tasks from the JSON file.
    Returns an empty list if the file doesn't exist, is empty, or contains invalid JSON.
    """
    if not os.path.exists(SCHEDULED_TASKS_FILE):
        return []
    try:
        with open(SCHEDULED_TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return []
            tasks = json.loads(content)
            if not isinstance(tasks, list):
                print(f"Warning: {SCHEDULED_TASKS_FILE} does not contain a JSON list. Resetting.")
                return []
            return tasks
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from {SCHEDULED_TASKS_FILE}. Returning empty list.")
        return []
    except Exception as e:
        print(f"Error loading tasks from {SCHEDULED_TASKS_FILE}: {e}")
        return []

def _save_tasks(tasks: List[Dict[str, Any]]):
    """
    Saves the provided list of tasks to the JSON file.
    """
    try:
        with open(SCHEDULED_TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
    except Exception as e:
        print(f"Error saving tasks to {SCHEDULED_TASKS_FILE}: {e}")

def _is_valid_vevent_basic(vevent_str: str) -> bool:
    """
    Performs a very basic validation of the VEVENT string.
    Checks for BEGIN:VEVENT, END:VEVENT, and DTSTART.
    """
    if not isinstance(vevent_str, str):
        return False
    return "BEGIN:VEVENT" in vevent_str and \
           "END:VEVENT" in vevent_str and \
           "DTSTART" in vevent_str

# --- Tool Functions ---

async def create_scheduled_task(conversation_id: str, user_prompt: str, schedule_vevent: str) -> Dict[str, Any]:
    """
    Creates a new scheduled task and saves it to the persistent store.

    Args:
        conversation_id (str): The ID of the conversation this task belongs to.
        user_prompt (str): The prompt string to be injected when the task is due.
        schedule_vevent (str): The full VEVENT string defining the schedule (DTSTART, RRULE, etc.).

    Returns:
        dict: A dictionary containing the status of the operation and task details if successful.
    """
    log_identifier = f"create_task_conv_{conversation_id}"
    print(f"\n[{log_identifier}] Attempting to create scheduled task...")

    if not all([conversation_id, user_prompt, schedule_vevent]):
        message = "Missing one or more required fields: conversation_id, user_prompt, or schedule_vevent."
        print(f"[{log_identifier}] Error: {message}")
        return {"status": "error", "message": message}

    if not _is_valid_vevent_basic(schedule_vevent):
        message = (
            "Invalid schedule_vevent format. "
            "It must be a string containing BEGIN:VEVENT, END:VEVENT, and DTSTART."
        )
        print(f"[{log_identifier}] Error: {message}")
        return {"status": "error", "message": message}

    tasks = await asyncio.to_thread(_load_tasks)

    new_task_id = str(uuid.uuid4())
    new_task = {
        "id": new_task_id,
        "conversation_id": conversation_id,
        "user_prompt": user_prompt,
        "schedule_vevent": schedule_vevent,
        "status": "pending"
    }

    tasks.append(new_task)
    await asyncio.to_thread(_save_tasks, tasks)

    print(f"[{log_identifier}] Successfully created task ID: {new_task_id}")
    return {
        "status": "success",
        "message": f"Scheduled task created successfully with ID: {new_task_id}.",
        "task_id": new_task_id,
        "task": new_task
    }

async def list_scheduled_tasks(conversation_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Lists all scheduled tasks, optionally filtered by conversation_id.

    Args:
        conversation_id (Optional[str]): If provided, only tasks for this conversation are returned.

    Returns:
        dict: A dictionary containing the status and a list of tasks.
    """
    log_identifier = f"list_tasks_conv_{conversation_id or 'all'}"
    print(f"\n[{log_identifier}] Attempting to list scheduled tasks...")

    tasks = await asyncio.to_thread(_load_tasks)

    if conversation_id:
        filtered_tasks = [task for task in tasks if task.get("conversation_id") == conversation_id]
        print(f"[{log_identifier}] Found {len(filtered_tasks)} tasks for conversation_id '{conversation_id}'.")
        return {
            "status": "success",
            "message": f"Found {len(filtered_tasks)} tasks for conversation_id '{conversation_id}'.",
            "tasks": filtered_tasks
        }
    else:
        print(f"[{log_identifier}] Found {len(tasks)} total tasks.")
        return {
            "status": "success",
            "message": f"Found {len(tasks)} total tasks.",
            "tasks": tasks
        }

async def delete_scheduled_task(task_id: str) -> Dict[str, Any]:
    """
    Deletes a scheduled task by its ID.

    Args:
        task_id (str): The UUID of the task to delete.

    Returns:
        dict: A dictionary containing the status of the operation.
    """
    log_identifier = f"delete_task_{task_id}"
    print(f"\n[{log_identifier}] Attempting to delete scheduled task ID: {task_id}")

    if not task_id:
        message = "Task ID cannot be empty."
        print(f"[{log_identifier}] Error: {message}")
        return {"status": "error", "message": message}

    tasks = await asyncio.to_thread(_load_tasks)
    
    initial_task_count = len(tasks)
    tasks_after_deletion = [task for task in tasks if task.get("id") != task_id]

    if len(tasks_after_deletion) == initial_task_count:
        message = f"Task ID '{task_id}' not found."
        print(f"[{log_identifier}] Error: {message}")
        return {"status": "error", "message": message}

    await asyncio.to_thread(_save_tasks, tasks_after_deletion)

    print(f"[{log_identifier}] Successfully deleted task ID: {task_id}")
    return {
        "status": "success",
        "message": f"Scheduled task ID '{task_id}' deleted successfully."
    }