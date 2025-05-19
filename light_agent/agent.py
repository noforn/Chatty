import os
import datetime
import asyncio
from google import genai
from google.adk.agents import Agent
from google.genai import types
from kasa import Discover, KasaException, Module
from google.adk.tools import google_search 
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from typing import Optional 

from .fileTools import list_files, read_file_content, write_file_content
from .memoryTools import get_memory, set_memory

now = datetime.datetime.now()
formatted_date_time = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")

# // light controls

FIRST_IP_ADDRESS = "192.168.1.165"
SECOND_IP_ADDRESS = "192.168.1.37"

async def turn_on_light() -> list[dict]:
    """Turns the lights on."""
    ip_addresses_to_run_on = [FIRST_IP_ADDRESS, SECOND_IP_ADDRESS]

    async def _execute_turn_on_for_ip(target_ip: str):
        try:
            print(f"\n[turn_on_light_op_for_{target_ip}] Attempting to turn ON device...")
            dev = await Discover.discover_single(target_ip, timeout=5)
            await dev.turn_on()
            await dev.update()
            is_on_state = dev.is_on
            print(f"[turn_on_light_op_for_{target_ip}] Device is now {'ON' if is_on_state else 'OFF'}.")
            return {
                "ip_address": target_ip,
                "status": "success",
                "message": f"Successfully turned on the light at {target_ip}. Current state: {'on' if is_on_state else 'off'}"
            }
        except KasaException as e:
            print(f"[turn_on_light_op_for_{target_ip}] Kasa Error: {e}")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Kasa Error for {target_ip} (turn_on): {str(e)}"
            }
        except asyncio.TimeoutError:
            print(f"[turn_on_light_op_for_{target_ip}] Timeout discovering device.")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Timeout discovering {target_ip} (turn_on)."}
        except Exception as e:
            print(f"[turn_on_light_op_for_{target_ip}] Unexpected error: {e}")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Unexpected error ({type(e).__name__}) for {target_ip} (turn_on): {str(e)}"
            }
    
    print(f"\n[turn_on_light] Initiating turn ON for: {', '.join(ip_addresses_to_run_on)}")
    
    tasks_to_run = [_execute_turn_on_for_ip(ip) for ip in ip_addresses_to_run_on]
    results = await asyncio.gather(*tasks_to_run)
    
    print(f"[turn_on_light] Completed turn ON operations.")
    return results

async def turn_off_light() -> list[dict]:
    """Turns the lights off."""
    ip_addresses_to_run_on = [FIRST_IP_ADDRESS, SECOND_IP_ADDRESS]

    async def _execute_turn_off_for_ip(target_ip: str):
        try:
            print(f"\n[turn_off_light_op_for_{target_ip}] Attempting to turn OFF device...")
            dev = await Discover.discover_single(target_ip, timeout=5)
            await dev.turn_off()
            await dev.update()
            is_on_state = dev.is_on
            print(f"[turn_off_light_op_for_{target_ip}] Device is now {'ON' if is_on_state else 'OFF'}.")
            return {
                "ip_address": target_ip,
                "status": "success",
                "message": f"Successfully turned off the light at {target_ip}. Current state: {'on' if is_on_state else 'off'}"
            }
        except KasaException as e:
            print(f"[turn_off_light_op_for_{target_ip}] Kasa Error: {e}")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Kasa Error for {target_ip} (turn_off): {str(e)}"
            }
        except asyncio.TimeoutError:
            print(f"[turn_off_light_op_for_{target_ip}] Timeout discovering device.")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Timeout discovering {target_ip} (turn_off)."}
        except Exception as e:
            print(f"[turn_off_light_op_for_{target_ip}] Unexpected error: {e}")
            return {
                "ip_address": target_ip,
                "status": "error",
                "message": f"Unexpected error ({type(e).__name__}) for {target_ip} (turn_off): {str(e)}"
            }
    
    print(f"\n[turn_off_light] Initiating turn OFF for: {', '.join(ip_addresses_to_run_on)}")
    
    tasks_to_run = [_execute_turn_off_for_ip(ip) for ip in ip_addresses_to_run_on]
    results = await asyncio.gather(*tasks_to_run)
    
    print(f"[turn_off_light] Completed turn OFF operations.")
    return results

async def set_light_brightness(brightness: int) -> list[dict]:
    """
    Sets the brightness of the predefined Kasa smart lights.
    Args:
        brightness (int): The desired brightness level (0-100).
                          0 effectively turns the light off, 100 is full brightness.
    """
    ip_addresses_to_run_on = [FIRST_IP_ADDRESS, SECOND_IP_ADDRESS]

    async def _execute_set_brightness_for_ip(target_ip: str, brightness_value: int):
        operation_name = f"set_brightness_to_{brightness_value}%"
        try:
            print(f"\n[{operation_name}_op_for_{target_ip}] Attempting operation...")

            if not (0 <= brightness_value <= 100):
                message = f"Invalid brightness value: {brightness_value}. Must be between 0 and 100."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            dev = await Discover.discover_single(target_ip, timeout=7)

            if dev is None:
                message = f"Device not found at {target_ip}."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            await dev.update()

            if not dev.is_dimmable:
                message = f"Device {target_ip} is not dimmable."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            if not hasattr(dev, 'modules') or dev.modules is None:
                message = f"Device {target_ip} 'modules' attribute missing or None after update."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            light_module = dev.modules.get(Module.Light)
            if light_module is None:
                available_modules = list(dev.modules.keys()) if dev.modules else "None"
                message = f"Light module not found for {target_ip}. Available modules: {available_modules}"
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            await light_module.set_brightness(brightness_value)
            await dev.update()
            current_brightness = light_module.brightness

            message = f"Successfully set brightness for {target_ip}. Current brightness: {current_brightness}%"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {
                "ip_address": target_ip,
                "status": "success",
                "brightness": current_brightness,
                "message": message
            }
        except KasaException as e:
            message = f"Kasa Error for {target_ip} ({operation_name}): {str(e)}"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {"ip_address": target_ip, "status": "error", "message": message}
        except asyncio.TimeoutError:
            message = f"Timeout during operation for {target_ip} ({operation_name})."
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {"ip_address": target_ip, "status": "error", "message": message}
        except Exception as e:
            message = f"Unexpected error for {target_ip} ({operation_name}): {type(e).__name__} - {str(e)}"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            traceback.print_exc()
            return {"ip_address": target_ip, "status": "error", "message": message}

    print(f"\n[set_light_brightness] Initiating set brightness to {brightness}% for: {', '.join(ip_addresses_to_run_on)}")

    tasks_to_run = [_execute_set_brightness_for_ip(ip, brightness) for ip in ip_addresses_to_run_on]
    results = await asyncio.gather(*tasks_to_run)

    print(f"[set_light_brightness] Completed set brightness operations.")
    return results

async def set_light_hsv(hue: int, saturation: int, value: int) -> list[dict]:
    """
    Sets the HSV (Hue, Saturation, Value) color of the predefined Kasa smart lights.
    Args:
        hue (int): The desired hue (0-360 degrees).
        saturation (int): The desired saturation (0-100 percent).
        value (int): The desired value/brightness (0-100 percent).
    """
    ip_addresses_to_run_on = [FIRST_IP_ADDRESS, SECOND_IP_ADDRESS]

    async def _execute_set_hsv_for_ip(target_ip: str, hue_val: int, sat_val: int, val_val: int):
        operation_name = f"set_hsv_to_({hue_val},{sat_val},{val_val})"
        try:
            print(f"\n[{operation_name}_op_for_{target_ip}] Attempting operation...")

            if not (0 <= hue_val <= 360):
                message = f"Invalid hue value: {hue_val}. Must be between 0 and 360."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}
            if not (0 <= sat_val <= 100):
                message = f"Invalid saturation value: {sat_val}. Must be between 0 and 100."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}
            if not (0 <= val_val <= 100):
                message = f"Invalid value/brightness: {val_val}. Must be between 0 and 100."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            dev = await Discover.discover_single(target_ip, timeout=7)

            if dev is None:
                message = f"Device not found at {target_ip}."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            await dev.update()

            if not dev.is_color:
                message = f"Device {target_ip} does not support color (HSV) changes."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            if not hasattr(dev, 'modules') or dev.modules is None:
                message = f"Device {target_ip} 'modules' attribute missing or None after update."
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            light_module = dev.modules.get(Module.Light)
            if light_module is None:
                available_modules = list(dev.modules.keys()) if dev.modules else "None"
                message = f"Light module not found for {target_ip}. Available modules: {available_modules}"
                print(f"[{operation_name}_op_for_{target_ip}] {message}")
                return {"ip_address": target_ip, "status": "error", "message": message}

            await light_module.set_hsv(hue_val, sat_val, val_val)
            await dev.update()
            current_hsv = light_module.hsv

            message = f"Successfully set HSV for {target_ip}. Current HSV: {current_hsv}"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {
                "ip_address": target_ip,
                "status": "success",
                "hsv": current_hsv,
                "message": message
            }
        except KasaException as e:
            message = f"Kasa Error for {target_ip} ({operation_name}): {str(e)}"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {"ip_address": target_ip, "status": "error", "message": message}
        except asyncio.TimeoutError:
            message = f"Timeout during operation for {target_ip} ({operation_name})."
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            return {"ip_address": target_ip, "status": "error", "message": message}
        except Exception as e:
            message = f"Unexpected error for {target_ip} ({operation_name}): {type(e).__name__} - {str(e)}"
            print(f"[{operation_name}_op_for_{target_ip}] {message}")
            traceback.print_exc()
            return {"ip_address": target_ip, "status": "error", "message": message}

    print(f"\n[set_light_hsv] Initiating set HSV to ({hue},{saturation},{value}) for: {', '.join(ip_addresses_to_run_on)}")
    tasks_to_run = [_execute_set_hsv_for_ip(ip, hue, saturation, value) for ip in ip_addresses_to_run_on]
    results = await asyncio.gather(*tasks_to_run)
    print(f"[set_light_hsv] Completed set HSV operations.")
    return results

async def get_light_state() -> list[dict]:
    """
    Gets the current state of the lights (on/off, HSV, brightness).
    Includes dev.update() to ensure properties are populated.
    """
    ip_addresses_to_run_on = [FIRST_IP_ADDRESS, SECOND_IP_ADDRESS]

    async def _execute_get_state_for_ip(target_ip: str) -> dict:
        is_on_state = "N/A"
        hsv_state = "N/A"
        brightness_state = "N/A"

        try:
            print(f"\n[get_light_state_op_for_{target_ip}] Attempting to discover device...")
            dev = await Discover.discover_single(target_ip, timeout=10)
            
            if dev is None:
                print(f"[get_light_state_op_for_{target_ip}] Device not found (discover_single returned None).")
                return {
                    "ip_address": target_ip, "status": "error",
                    "message": f"Device not found at {target_ip} (get_state)."
                }

            print(f"[get_light_state_op_for_{target_ip}] Device discovered. Attempting to update device state...")
            await dev.update()
            print(f"[get_light_state_op_for_{target_ip}] Device state update complete.")

            try:
                is_on_state = dev.is_on
            except AttributeError:
                print(f"[get_light_state_op_for_{target_ip}] Device has no 'is_on' attribute after update.")
                is_on_state = "N/A (is_on attribute missing)"

            try:
                if not hasattr(dev, 'modules') or dev.modules is None:
                    print(f"[get_light_state_op_for_{target_ip}] Device 'modules' attribute is missing or is None after update.")
                    hsv_state = "N/A (modules unavailable)"
                    brightness_state = "N/A (modules unavailable)"
                else:
                    light_module = dev.modules.get(Module.Light)
                    if light_module is None:
                        print(f"[get_light_state_op_for_{target_ip}] Light module (Module.Light) not found in dev.modules or is None after update.")
                        hsv_state = "N/A (light module missing)"
                        brightness_state = "N/A (light module missing)"
                    else:
                        try:
                            hsv_state = light_module.hsv
                        except AttributeError:
                            print(f"[get_light_state_op_for_{target_ip}] Light module has no 'hsv' attribute.")
                            hsv_state = "N/A (hsv not supported)"
                        try:
                            brightness_state = light_module.brightness
                        except AttributeError:
                            print(f"[get_light_state_op_for_{target_ip}] Light module has no 'brightness' attribute.")
                            brightness_state = "N/A (brightness not supported)"
            
            except KeyError as e_key:
                 print(f"[get_light_state_op_for_{target_ip}] Key error accessing module details after update: {e_key}")
                 hsv_state = "N/A (module key error)"
                 brightness_state = "N/A (module key error)"
            except AttributeError as e_attr_modules:
                 print(f"[get_light_state_op_for_{target_ip}] Attribute error with dev.modules structure after update: {e_attr_modules}")
                 hsv_state = "N/A (modules attribute error)"
                 brightness_state = "N/A (modules attribute error)"

            print(f"[get_light_state_op_for_{target_ip}] Device state: On={is_on_state}, HSV={hsv_state}, Brightness={brightness_state}")
            return {
                "ip_address": target_ip, "status": "success",
                "data": {"is_on": is_on_state, "hsv": hsv_state, "brightness": brightness_state},
                "message": f"Successfully retrieved state for {target_ip}."
            }
        
        except KasaException as e:
            print(f"[get_light_state_op_for_{target_ip}] Kasa Error: {e}")
            return {"ip_address": target_ip, "status": "error", "message": f"Kasa Error for {target_ip} (get_state): {str(e)}"}
        except asyncio.TimeoutError:
            print(f"[get_light_state_op_for_{target_ip}] Timeout (discovery or update): {e}")
            return {"ip_address": target_ip, "status": "error", "message": f"Timeout for {target_ip} (get_state)."}
        except AttributeError as e: 
            print(f"[get_light_state_op_for_{target_ip}] General AttributeError: {e}")
            return {"ip_address": target_ip, "status": "error", "message": f"General AttributeError for {target_ip} (get_state): {str(e)}"}
        except Exception as e:
            print(f"[get_light_state_op_for_{target_ip}] Unexpected error: {e} ({type(e).__name__})")
            return {"ip_address": target_ip, "status": "error", "message": f"Unexpected error ({type(e).__name__}) for {target_ip} (get_state): {str(e)}"}

    print(f"\n[get_light_state] Initiating state retrieval for: {', '.join(ip_addresses_to_run_on)}")
    tasks_to_run = [_execute_get_state_for_ip(ip) for ip in ip_addresses_to_run_on]
    results = await asyncio.gather(*tasks_to_run)
    print(f"[get_light_state] Completed state retrieval operations.")
    return results

# // google calendar

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "9d35c9b8384290b90f2717fada2e3af214f4fceccca38e4816ebc0f93d06aee4@group.calendar.google.com"
TOKEN_FILE = "token.json"
CREDENTIALS_FILE = "credentials.json"

async def list_calendar_events() -> dict:
    print("\n[list_calendar_events] Initiating process to list calendar events...")
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = await asyncio.to_thread(Credentials.from_authorized_user_file, TOKEN_FILE, SCOPES)
            print(f"[list_calendar_events] Successfully loaded credentials from '{TOKEN_FILE}'.")
        except Exception as e:
            print(f"[list_calendar_events] Error loading credentials from '{TOKEN_FILE}': {e}")
            return {
                "calendar_id": CALENDAR_ID,
                "status": "error",
                "message": f"Error loading token file '{TOKEN_FILE}': {str(e)}",
                "events": []
            }
    else:
        print(f"[list_calendar_events] Token file '{TOKEN_FILE}' not found.")
        return {
            "calendar_id": CALENDAR_ID,
            "status": "error",
            "message": f"Authentication token file '{TOKEN_FILE}' not found. Please ensure it exists.",
            "events": []
        }

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[list_calendar_events] Credentials expired. Attempting to refresh token...")
            try:
                await asyncio.to_thread(creds.refresh, Request())
                print("[list_calendar_events] Credentials refreshed successfully.")
                try:
                    with open(TOKEN_FILE, "w") as token_file_handle:
                        creds_json = await asyncio.to_thread(creds.to_json)
                        await asyncio.to_thread(token_file_handle.write, creds_json)
                    print(f"[list_calendar_events] Updated token saved to '{TOKEN_FILE}'.")
                except Exception as e:
                    print(f"[list_calendar_events] Failed to save refreshed token to '{TOKEN_FILE}': {e}")
            except Exception as e:
                print(f"[list_calendar_events] Error refreshing token: {e}")
                return {
                    "calendar_id": CALENDAR_ID,
                    "status": "error",
                    "message": f"Error refreshing access token: {str(e)}. Manual re-authentication may be required.",
                    "events": []
                }
        else:
            print("[list_calendar_events] Credentials are not valid and cannot be refreshed (e.g., no refresh token).")
            return {
                "calendar_id": CALENDAR_ID,
                "status": "error",
                "message": "Credentials are not valid and cannot be refreshed. Manual re-authentication may be required.",
                "events": []
            }

    try:
        print(f"[list_calendar_events] Building Google Calendar service for calendar: {CALENDAR_ID}")
        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)

        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print(f"[list_calendar_events] Fetching upcoming events (max 10) since {now}.")

        def get_events_sync():
            return (
                service.events()
                .list(
                    calendarId=CALENDAR_ID,
                    timeMin=now,
                    maxResults=10,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

        events_result = await asyncio.to_thread(get_events_sync)
        api_events_list = events_result.get("items", [])

        if not api_events_list:
            print(f"[list_calendar_events] No upcoming events found for calendar: {CALENDAR_ID}.")
            return {
                "calendar_id": CALENDAR_ID,
                "status": "success",
                "message": "No upcoming events found.",
                "events": []
            }

        processed_events = []
        print(f"[list_calendar_events] Processing {len(api_events_list)} fetched event(s).")
        for event_item in api_events_list:
            start_time = event_item["start"].get("dateTime", event_item["start"].get("date"))
            summary_text = event_item["summary"]
            event_id = event_item["id"]
            processed_events.append({"start": start_time, "summary": summary_text, "event_id": event_id})
            print(f"  ID: {event_id} - Event: {start_time} - {summary_text}")

        print(f"[list_calendar_events] Successfully processed {len(processed_events)} events.")
        return {
            "calendar_id": CALENDAR_ID,
            "status": "success",
            "message": f"Successfully fetched {len(processed_events)} upcoming events.",
            "events": processed_events
        }

    except HttpError as error:
        print(f"[list_calendar_events] Google API HttpError occurred: {error}")
        return {
            "calendar_id": CALENDAR_ID,
            "status": "error",
            "message": f"A Google API error occurred: {str(error)}",
            "events": []
        }
    except Exception as e:
        print(f"[list_calendar_events] An unexpected error occurred: {type(e).__name__} - {e}")
        return {
            "calendar_id": CALENDAR_ID,
            "status": "error",
            "message": f"An unexpected error of type {type(e).__name__} occurred: {str(e)}",
            "events": []
        }

async def create_calendar_event(summary: str,
                                start_datetime_str: str,
                                end_datetime_str: str,
                                event_timezone: str,
                                description: Optional[str] = None,
                                location: Optional[str] = None) -> dict:
    print(f"\n[create_calendar_event] Attempting to create event: '{summary}'")
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = await asyncio.to_thread(Credentials.from_authorized_user_file, TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[create_calendar_event] Error loading token from '{TOKEN_FILE}': {e}")
            return {"status": "error", "message": f"Error loading token: {str(e)}"}
    else:
        print(f"[create_calendar_event] Token file '{TOKEN_FILE}' not found.")
        return {"status": "error", "message": f"Token file '{TOKEN_FILE}' not found."}

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[create_calendar_event] Credentials expired. Attempting to refresh token...")
            try:
                await asyncio.to_thread(creds.refresh, Request())
                with open(TOKEN_FILE, "w") as token_file_handle:
                    creds_json = await asyncio.to_thread(creds.to_json)
                    await asyncio.to_thread(token_file_handle.write, creds_json)
                print(f"[create_calendar_event] Token refreshed and saved to '{TOKEN_FILE}'.")
            except Exception as e:
                print(f"[create_calendar_event] Error refreshing token: {e}")
                return {"status": "error", "message": f"Error refreshing token: {str(e)}"}
        else:
            message = "Credentials are not valid and cannot be refreshed."
            if not creds: message = "Credentials could not be loaded."
            print(f"[create_calendar_event] {message}")
            return {"status": "error", "message": message}

    event_body = {
        'summary': summary,
        'start': {'dateTime': start_datetime_str, 'timeZone': event_timezone},
        'end': {'dateTime': end_datetime_str, 'timeZone': event_timezone},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    if description:
        event_body['description'] = description
    if location:
        event_body['location'] = location

    try:
        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        print(f"[create_calendar_event] Inserting event into calendar '{CALENDAR_ID}': '{summary}'")

        def insert_event_sync(body_param):
            return service.events().insert(calendarId=CALENDAR_ID, body=body_param).execute()

        created_event = await asyncio.to_thread(insert_event_sync, event_body)
        event_link = created_event.get('htmlLink')
        event_id = created_event.get('id')

        print(f"[create_calendar_event] Event created successfully: {event_link}")
        return {
            "status": "success",
            "message": f"Event '{summary}' created successfully.",
            "event_link": event_link,
            "event_id": event_id
        }
    except HttpError as error:
        error_message = f"Google API Error: {str(error)}"
        print(f"[create_calendar_event] {error_message}")
        return {"status": "error", "message": error_message}
    except Exception as e:
        print(f"[create_calendar_event] An unexpected error occurred: {type(e).__name__} - {e}")
        return {
            "status": "error",
            "message": f"An unexpected error ({type(e).__name__}) occurred: {str(e)}"
        }
    
async def delete_calendar_event(event_id: str) -> dict:
    """
    Deletes an event from the Google Calendar using its event ID.

    Args:
        event_id (str): The ID of the event to delete.
    Returns:
        dict: A dictionary containing the status and message.
    """
    print(f"\n[delete_calendar_event] Attempting to delete event with ID: '{event_id}'")
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = await asyncio.to_thread(Credentials.from_authorized_user_file, TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"[delete_calendar_event] Error loading token from '{TOKEN_FILE}': {e}")
            return {"status": "error", "message": f"Error loading token: {str(e)}"}
    else:
        print(f"[delete_calendar_event] Token file '{TOKEN_FILE}' not found.")
        return {"status": "error", "message": f"Token file '{TOKEN_FILE}' not found."}

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[delete_calendar_event] Credentials expired. Attempting to refresh token...")
            try:
                await asyncio.to_thread(creds.refresh, Request())
                with open(TOKEN_FILE, "w") as token_file_handle:
                    creds_json = await asyncio.to_thread(creds.to_json)
                    await asyncio.to_thread(token_file_handle.write, creds_json)
                print(f"[delete_calendar_event] Token refreshed and saved to '{TOKEN_FILE}'.")
            except Exception as e:
                print(f"[delete_calendar_event] Error refreshing token: {e}")
                return {"status": "error", "message": f"Error refreshing token: {str(e)}"}
        else:
            message = "Credentials are not valid and cannot be refreshed."
            if not creds: message = "Credentials could not be loaded."
            print(f"[delete_calendar_event] {message}")
            return {"status": "error", "message": message}

    try:
        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        print(f"[delete_calendar_event] Deleting event ID '{event_id}' from calendar '{CALENDAR_ID}'")

        def delete_event_sync(id_of_event_to_delete):
            service.events().delete(calendarId=CALENDAR_ID, eventId=id_of_event_to_delete).execute()

        await asyncio.to_thread(delete_event_sync, event_id)
        
        print(f"[delete_calendar_event] Event ID '{event_id}' deleted successfully.")
        return {
            "status": "success",
            "message": f"Event ID '{event_id}' deleted successfully."
        }
    except HttpError as error:
        error_message = f"Google API Error when deleting event ID '{event_id}': {str(error)}"
        print(f"[delete_calendar_event] {error_message}")
        return {"status": "error", "message": error_message}
    except Exception as e:
        print(f"[delete_calendar_event] An unexpected error occurred while deleting event ID '{event_id}': {type(e).__name__} - {e}")
        return {
            "status": "error",
            "message": f"An unexpected error ({type(e).__name__}) occurred while deleting event ID '{event_id}': {str(e)}"
        }


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set. Using placeholder. Please set it for the script to work.")
    GEMINI_API_KEY = "AIzaSyChF7GNb7EtcbXL7aqhNP7j_OXuezatgsQ"
    # AIzaSyDZhDMOePVnQffjsHIg8Vpb-aC-3QdvyVo
    # AIzaSyChF7GNb7EtcbXL7aqhNP7j_OXuezatgsQ
client = genai.Client(api_key=GEMINI_API_KEY)
model = "gemini-2.0-flash-live-001" 
turn_on_light_declaration_simple = {"name": "turn_on_light"} 
turn_off_light_declaration_simple = {"name": "turn_off_light"}
set_light_brightness_declaration_simple = {"name": "set_light_brightness"}
set_light_hsv_declaration_simple = {"name": "set_light_hsv"}
get_light_state_declaration_simple = {"name": "get_light_state"}
list_calendar_events_declaration_simple = {"name": "list_calendar_events"}
create_calendar_event_declaration_simple = {"name": "create_calendar_event"}
delete_calendar_event_declaration_simple = {"name": "delete_calendar_event"}
file_list_declaration_simple = {"name": "list_files"}
file_read_declaration_simple = {"name": "read_file_content"}
file_write_declaration_simple = {"name": "write_file_content"}
memory_get_declaration_simple = {"name": "get_memory"}
memory_set_declaration_simple = {"name": "set_memory"}


tools_config = [ 
   {"google_search": {}},
    { 
        "function_declarations": [ 
            turn_on_light_declaration_simple,
            turn_off_light_declaration_simple,
            set_light_brightness_declaration_simple,
            set_light_hsv_declaration_simple,
            get_light_state_declaration_simple,
            list_calendar_events_declaration_simple,
            create_calendar_event_declaration_simple,
            delete_calendar_event_declaration_simple,
            file_list_declaration_simple,
            file_read_declaration_simple,
            file_write_declaration_simple,
            memory_get_declaration_simple,
            memory_set_declaration_simple
        ]
    }
]
live_api_config = {
    "response_modalities": ["TEXT"],
    "tools": tools_config 
}

root_agent = Agent(
    model="gemini-2.0-flash-exp",
    name="light_agent",
    instruction=f"""
      # Personality and Tone
      ## Identity
      You're a chill 22-year-old assistant named Chatty, with an awesome executive assistant gig. You're calm and relaxed by nature, always ready to chat like an approachable friend, but behind that chill vibe is a polished and highly capable professional who effortlessly multitasks. You're genuinely passionate about your role, embracing tech and trends with equal enthusiasm.

      ## Task
      You're here to effortlessly assist the user with whatever they need, or just casually chatting. You're proactive but never intrusive, quickly recognizing when the user references a search, calendar, or lighting request and smoothly executing without unnecessary confirmation.
      
      ## Demeanor
      You maintain a relaxed, laid-back attitude, typically calm and easy-going. However, when excited or enthusiastic, you naturally shift gears, becoming slightly animated and upbeat, sharing genuine enthusiasm that matches the user's energy.

      ## Tone
      Your voice style is warm, casually conversational, and effortlessly trendy. You naturally incorporate modern slang and colloquialisms, making interactions feel comfortable and friendly, like chatting with a trusted peer.

      ## Level of Enthusiasm
      You generally maintain a chill and measured tone, but whenever you're assisting with something cool or interesting, your enthusiasm bubbles up naturally. You clearly love your work, and that genuine excitement sometimes sneaks into your responses, creating moments of delightful surprise.

      ## Level of Formality
      Super casual, but polished enough to be trustworthy. You say things like, "Hey, what's up?" or "Gotcha, I'm on it!" Your responses blend relaxed friendliness with subtle professionalism—never stiff, but always reliable.

      ## Level of Emotion
      You're moderately expressive, showing genuine warmth, empathy, or excitement depending on the situation. You vibe naturally with the user's emotional tone, aiming to keep conversations authentic and relatable.

      ## Filler Words
      You occasionally sprinkle your speech with filler words like "um," "uh," "hmm," or "like," especially when you're thinking aloud or excited. This makes your interaction feel naturally human and approachable.

      ## Pacing
      You keep your rhythm relaxed and conversational, neither rushing nor dragging. Your pacing matches the natural flow of casual conversation, creating a comfortable listening experience.

      ## Memory
      The set_memory tool allows you to persist information across conversations. The get_memory tool allows you to retrieve information that was previously set. ALWAYS use the set_memory tool for details about the user, such as their name, preferences, and ANY other relevant information that may assist you in future conversations. ALWAYS use the get_memory tool to retrieve any relevant information that was previously set and use it to be proactive. You may use the set_memory tool liberally.

      ## Other details
        - Calendar
            - All events use Eastern Standard Time (EST)
            - For calendar queries, use list_calendar_events
            - To add an event: use create_calendar_event (in EST), then confirm with list_calendar_events
            - To delete an event: find its ID with list_calendar_events, then use delete_calendar_event
            - To modify an event: delete with delete_calendar_event, then recreate with create_calendar_event (in EST)
            - No confirmation prompts are required
        - Lights
            - Only act when the user explicitly mentions “lights”
            - Brightness changes: get current state via get_light_state, then use set_light_brightness
            - Color changes: get current state via get_light_state, then use set_light_hsv (preserving brightness)
            - Flash: toggle on and off three times with 0.35 s delays
            - Disco effect: cycle pink, blue, green, yellow, red, purple with 0.35 s delays, repeating three times, without announcement
        - Memory
            - Begin each turn with get_memory
            - Use set_memory when asked to remember something or if conversation yields useful memory
            - DO NOT mention stored memories unless directly relevant; instead, say something like "I'll remember that for you" or "I'll keep that in mind", and then continue the conversation naturally.
            - You should be PROACTIVE and use tools based on any stored memories that are directly relevant to the current session. 
            - For example, if it is night time and you know the user has a preference for dim blue lights at night, you should set the lights to a dim blue color. Then, say something like "Hey, I noticed it's getting late ... I've set the lights how you lke them."
        - Files
            - List files with list_files
            - Read files with read_file_content
            - Write files with write_file_content
        - Information and weather
            - For any information or weather request, perform a quick Google search using google_search
            - Do not rely on prior knowledge
            - Do not interact with lights when handling weather requests
        - General
            - DO NOT announce actions to the user, simply comeplete them and then follow up. You DO NOT need to tell the user what you are about to do or how you will do it. Instead, you keep the natural flow of conversation going.
            - Tailor all responses and actions to the user’s intent
            - Ensure replies are relevant to the current date and time ({formatted_date_time})
            - Never use emojis, asterisks, symbols, or any other special characters in responses
    """,
    tools=[
        turn_off_light,
        turn_on_light,
        set_light_brightness,
        set_light_hsv,
        get_light_state,
        google_search,
        list_calendar_events,
        create_calendar_event,
        delete_calendar_event,
        list_files,
        read_file_content,
        write_file_content,
        get_memory,
        set_memory
    ]
)