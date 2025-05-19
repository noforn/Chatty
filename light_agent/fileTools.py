import asyncio
import os
from google import genai
from google.genai import types

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def list_files():
    """
    Asynchronously lists files in the 'agent-files/' directory.
    This function directly performs the operation for the specified directory,
    following the error handling and return structure of the provided example.

    Returns:
        dict: A dictionary containing the operation status, directory path,
              a message, and a list of files if successful.
    """
    target_dir = "agent-files/"
    log_identifier = "agent_files" 

    try:
        print(f"\n[list_files_op_for_{log_identifier}] Attempting to list files in directory: {target_dir}")
        
        files = await asyncio.to_thread(os.listdir, target_dir)
        
        print(f"[list_files_op_for_{log_identifier}] Successfully listed {len(files)} item(s) in '{target_dir}'.")
        return {
            "directory_path": target_dir,
            "status": "success",
            "files": files,
            "message": f"Successfully listed files in '{target_dir}'. Found {len(files)} item(s)."
        }
    except FileNotFoundError:
        print(f"[list_files_op_for_{log_identifier}] Error: Directory not found: {target_dir}")
        return {
            "directory_path": target_dir,
            "status": "error",
            "files": [],
            "message": f"Directory not found: '{target_dir}'."
        }
    except PermissionError:
        print(f"[list_files_op_for_{log_identifier}] Error: Permission denied for directory: {target_dir}")
        return {
            "directory_path": target_dir,
            "status": "error",
            "files": [],
            "message": f"Permission denied for directory: '{target_dir}'."
        }
    except Exception as e:
        print(f"[list_files_op_for_{log_identifier}] Unexpected error while listing files in '{target_dir}': {e}")
        return {
            "directory_path": target_dir,
            "status": "error",
            "files": [],
            "message": f"Unexpected error ({type(e).__name__}) for '{target_dir}' (list_files): {str(e)}"
        }

async def read_file_content(filename: str):
    """
    Asynchronously reads the content of a specified file from the 'agent-files/' directory.
    Assumes the file is text-based and uses UTF-8 encoding.

    Important Security Note:
        This function is designed to read files only from the 'agent-files/' subdirectory.
        It includes internal validation to prevent path traversal attacks. Ensure that
        the 'filename' argument, if sourced from an LLM or external input,
        is handled with awareness of this constrained environment.

    Args:
        filename (str): The name of the file (e.g., "myfile.txt") or a relative path
                        within 'agent-files/' (e.g., "subdir/myfile.txt") to be read.
                        It should not be an absolute path or attempt to navigate
                        outside 'agent-files/'.

    Returns:
        dict: A dictionary containing:
              - "file_path" (str): The original filename argument provided.
              - "status" (str): "success" or "error".
              - "content" (str | None): The content of the file if successful,
                                        None otherwise.
              - "message" (str): A descriptive message about the operation.
    """
    agent_base_dir = "agent-files"

    log_identifier_base = os.path.basename(filename) if filename else "unknown_file_in_agent_files"
    log_identifier = "".join(c if c.isalnum() or c in ['_', '.'] else '_' for c in log_identifier_base).strip('_')
    if not log_identifier:
        log_identifier = "file_in_agent_files"

    if not filename or filename == ".":
        print(f"\n[read_file_op_for_{log_identifier}] Error: Invalid filename provided for reading within '{agent_base_dir}'.")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"Invalid or empty filename '{filename}' provided. Must be a valid file name or relative path within '{agent_base_dir}/'."
        }

    prospective_path = os.path.join(agent_base_dir, filename)

    abs_prospective_path = os.path.abspath(prospective_path)
    abs_agent_base_dir = os.path.abspath(agent_base_dir)

    if not (abs_prospective_path.startswith(abs_agent_base_dir + os.sep) or abs_prospective_path == abs_agent_base_dir):
        print(f"\n[read_file_op_for_{log_identifier}] [*] SECURITY ALERT: Attempt to access path '{filename}' which resolves outside the designated '{agent_base_dir}' directory.")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"[*] SECURITY ALERT: Path '{filename}' is outside the allowed '{agent_base_dir}' directory. Good try though."
        }

    actual_file_to_read = abs_prospective_path

    try:
        print(f"\n[read_file_op_for_{log_identifier}] Attempting to read file: '{filename}' from '{agent_base_dir}/' (resolved to: {actual_file_to_read})")

        def _sync_read_file():
            with open(actual_file_to_read, 'r', encoding='utf-8') as f:
                return f.read()

        content = await asyncio.to_thread(_sync_read_file)

        print(f"[read_file_op_for_{log_identifier}] Successfully read file: '{filename}' from '{agent_base_dir}/'")
        return {
            "file_path": filename,
            "status": "success",
            "content": content,
            "message": f"Successfully read content from '{filename}' in '{agent_base_dir}/'."
        }
    except FileNotFoundError:
        print(f"[read_file_op_for_{log_identifier}] Error: File not found: '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_read})")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"File not found: '{filename}' in '{agent_base_dir}/'."
        }
    except IsADirectoryError:
        print(f"[read_file_op_for_{log_identifier}] Error: Specified path '{filename}' in '{agent_base_dir}/' is a directory, not a file (at path: {actual_file_to_read}).")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"Path '{filename}' in '{agent_base_dir}/' points to a directory, not a readable file."
        }
    except PermissionError:
        print(f"[read_file_op_for_{log_identifier}] Error: Permission denied for file: '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_read})")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"Permission denied when trying to read '{filename}' in '{agent_base_dir}/'."
        }
    except UnicodeDecodeError:
        print(f"[read_file_op_for_{log_identifier}] Error: Could not decode file '{filename}' in '{agent_base_dir}/' as UTF-8 (at path: {actual_file_to_read}). It might be a binary file or use a different text encoding.")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"Encoding error: Could not decode file '{filename}' in '{agent_base_dir}/' as UTF-8. It may not be a standard text file."
        }
    except IOError as e:
        print(f"[read_file_op_for_{log_identifier}] I/O Error reading file '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_read}): {e}")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"I/O Error reading file '{filename}' in '{agent_base_dir}/': {str(e)}"
        }
    except Exception as e:
        print(f"[read_file_op_for_{log_identifier}] Unexpected error while reading file '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_read}): {e}")
        return {
            "file_path": filename,
            "status": "error",
            "content": None,
            "message": f"Unexpected error ({type(e).__name__}) for '{filename}' in '{agent_base_dir}/' (read_file): {str(e)}"
        }

async def write_file_content(filename: str, content_to_write: str):
    """
    Asynchronously writes content to a specified file within the 'agent-files/' directory.
    If the file exists, it will be overwritten. If the file or its subdirectories
    do not exist, they will be created. Assumes UTF-8 encoding for the content.

    Important Security Note:
        This function is designed to write files only to the 'agent-files/' subdirectory.
        It includes internal validation to prevent path traversal attacks. Ensure that
        the 'filename' argument, if sourced from an LLM or external input,
        is handled with awareness of this constrained environment.

    Args:
        filename (str): The name of the file (e.g., "output.txt") or a relative path
                        within 'agent-files/' (e.g., "notes/draft.md") to which
                        content will be written. It should not be an absolute path
                        or attempt to navigate outside 'agent-files/'.
        content_to_write (str): The string content to write to the file.

    Returns:
        dict: A dictionary containing:
              - "file_path" (str): The original filename argument provided.
              - "status" (str): "success" or "error".
              - "message" (str): A descriptive message about the operation.
    """
    agent_base_dir = "agent-files"

    log_identifier_base = os.path.basename(filename) if filename else "unknown_file_to_write_in_agent_files"
    log_identifier = "".join(c if c.isalnum() or c in ['_', '.'] else '_' for c in log_identifier_base).strip('_')
    if not log_identifier:
        log_identifier = "file_to_write_in_agent_files"

    if not filename or filename == ".":
        print(f"\n[write_file_op_for_{log_identifier}] Error: Invalid filename provided for writing within '{agent_base_dir}'.")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Invalid or empty filename '{filename}' provided. Must be a valid file name or relative path within '{agent_base_dir}/'."
        }

    prospective_path = os.path.join(agent_base_dir, filename)
    abs_prospective_path = os.path.abspath(prospective_path)
    abs_agent_base_dir = os.path.abspath(agent_base_dir)

    if not (abs_prospective_path.startswith(abs_agent_base_dir + os.sep) or abs_prospective_path == abs_agent_base_dir):
        print(f"\n[write_file_op_for_{log_identifier}] Security Error: Attempt to write to path '{filename}' which resolves outside the designated '{agent_base_dir}' directory.")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Access denied: Path '{filename}' is outside the allowed '{agent_base_dir}' directory."
        }

    if abs_prospective_path == abs_agent_base_dir:
        print(f"\n[write_file_op_for_{log_identifier}] Error: Cannot write content directly to the directory '{agent_base_dir}'. A filename is required.")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Invalid operation: Cannot write content to the directory '{agent_base_dir}' (via filename '{filename}'); a filename is required."
        }

    actual_file_to_write = abs_prospective_path

    try:
        print(f"\n[write_file_op_for_{log_identifier}] Attempting to write to file: '{filename}' in '{agent_base_dir}/' (resolved to: {actual_file_to_write})")

        def _sync_write_file():
            parent_dir = os.path.dirname(actual_file_to_write)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(actual_file_to_write, 'w', encoding='utf-8') as f:
                f.write(content_to_write)

        await asyncio.to_thread(_sync_write_file)

        print(f"[write_file_op_for_{log_identifier}] Successfully wrote to file: '{filename}' in '{agent_base_dir}/'")
        return {
            "file_path": filename,
            "status": "success",
            "message": f"Successfully wrote content to '{filename}' in '{agent_base_dir}/'."
        }
    except IsADirectoryError:
        print(f"[write_file_op_for_{log_identifier}] Error: Specified path '{filename}' in '{agent_base_dir}/' is a directory, cannot overwrite with a file (at path: {actual_file_to_write}).")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Path '{filename}' in '{agent_base_dir}/' points to a directory; cannot write file content there."
        }
    except PermissionError:
        print(f"[write_file_op_for_{log_identifier}] Error: Permission denied for file: '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_write})")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Permission denied when trying to write to '{filename}' in '{agent_base_dir}/'."
        }
    except IOError as e:
        print(f"[write_file_op_for_{log_identifier}] I/O Error writing file '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_write}): {e}")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"I/O Error writing file '{filename}' in '{agent_base_dir}/': {str(e)}"
        }
    except Exception as e:
        print(f"[write_file_op_for_{log_identifier}] Unexpected error while writing file '{filename}' in '{agent_base_dir}/' (at path: {actual_file_to_write}): {e}")
        return {
            "file_path": filename,
            "status": "error",
            "message": f"Unexpected error ({type(e).__name__}) for '{filename}' in '{agent_base_dir}/' (write_file): {str(e)}"
        }

