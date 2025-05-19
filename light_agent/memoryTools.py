import os
import json
import asyncio

MEMORY_FILE = "agent_memory.json"

def _load_memory() -> dict:
    """
    Loads memory from the JSON file.
    Returns an empty dictionary if the file doesn't exist or is empty.
    """
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from {MEMORY_FILE}. Returning empty memory.")
        return {}
    except Exception as e:
        print(f"Error loading memory from {MEMORY_FILE}: {e}")
        return {}

def _save_memory(memory: dict):
    """
    Saves the provided memory dictionary to the JSON file.
    """
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2)
    except Exception as e:
        print(f"Error saving memory to {MEMORY_FILE}: {e}")

async def get_memory() -> dict:
    """
    Asynchronously returns stored memory by loading it from the memory file.
    This function is non-blocking for file I/O.
    """
    memory = await asyncio.to_thread(_load_memory)
    print(f"[get_memory] Memory loaded: {memory}")
    return memory

async def set_memory(key: str, value: str) -> dict:
    """
    Asynchronously sets a key-value pair in the memory.
    It loads the current memory, updates it with the string value, and saves it back.
    This function is non-blocking for file I/O.

    Args:
        key (str): The key to set in the memory.
        value (str): The string value to associate with the key.
                     If storing complex data, it should be pre-serialized to a JSON string.

    Returns:
        dict: A dictionary confirming the operation, including the key and value set.
    """
    memory = await asyncio.to_thread(_load_memory)
    
    memory[key] = value
    
    await asyncio.to_thread(_save_memory, memory)
    
    result = {"status": "success", "key": key, "value": value}
    print(f"[set_memory] Memory updated: {result}")
    return result

