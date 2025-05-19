import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

import requests
from dateutil import rrule
from dateutil.parser import isoparse
from icalendar import Event as iCalEvent
from icalendar.prop import vDDDTypes

SCHEDULED_TASKS_FILE = "scheduled_tasks.json"
POLL_INTERVAL_SECONDS = 10 # Keeping this for frequent checks during debug
MAIN_APP_INJECTION_URL = os.getenv("MAIN_APP_INJECTION_URL", "http://localhost:8000/api/inject-task-prompt")
REQUEST_TIMEOUT_SECONDS = 10

FIRED_ONCE_TASK_IDS = set()
# FIRED_ONCE_TASK_IDS = set() # Duplicate line, removed

# --- Helper Functions ---

def _load_tasks_for_scheduler() -> List[Dict[str, Any]]:
    if not os.path.exists(SCHEDULED_TASKS_FILE):
        print(f"Scheduler DEBUG (_load_tasks): {SCHEDULED_TASKS_FILE} not found.")
        return []
    try:
        with open(SCHEDULED_TASKS_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            if not content:
                print(f"Scheduler DEBUG (_load_tasks): {SCHEDULED_TASKS_FILE} is empty.")
                return []
            tasks = json.loads(content)
            if not isinstance(tasks, list):
                print(f"Scheduler Warning (_load_tasks): {SCHEDULED_TASKS_FILE} does not contain a JSON list. Resetting.")
                return []
            print(f"Scheduler DEBUG (_load_tasks): Loaded {len(tasks)} tasks.")
            # For more verbosity, you can print the tasks themselves:
            # for i, task_item in enumerate(tasks):
            #     print(f"Scheduler DEBUG (_load_tasks): Task {i}: {task_item.get('id')}, DTSTART (raw): {task_item.get('schedule_vevent', '').splitlines()[1 if 'DTSTART' in task_item.get('schedule_vevent','') else 0]}")
            return tasks
    except json.JSONDecodeError:
        print(f"Scheduler Warning (_load_tasks): Could not decode JSON from {SCHEDULED_TASKS_FILE}. Returning empty list.")
        return []
    except Exception as e:
        print(f"Scheduler Error (_load_tasks): Error loading tasks from {SCHEDULED_TASKS_FILE}: {e}")
        return []

def _make_dt_aware(dt_val: datetime, default_tz: timezone = timezone.utc) -> datetime:
    if dt_val.tzinfo is None or dt_val.tzinfo.utcoffset(dt_val) is None:
        # print(f"Scheduler DEBUG (_make_dt_aware): Making naive datetime {dt_val} aware with default_tz.")
        return dt_val.replace(tzinfo=default_tz)
    # print(f"Scheduler DEBUG (_make_dt_aware): Converting aware datetime {dt_val} to default_tz.")
    return dt_val.astimezone(default_tz)

def calculate_next_occurrence(task_id_for_debug: str, vevent_str: str, now_utc: datetime) -> Optional[datetime]:
    vevent_snippet_for_log = vevent_str[:80].replace("\n", " ") 
    print(f"\nScheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): VEVENT starts with: {vevent_snippet_for_log}")
    print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): now_utc = {now_utc.isoformat()}")
    try:
        event = iCalEvent.from_ical(vevent_str)
        dtstart_obj = event.get('dtstart')
        if not dtstart_obj:
            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): No DTSTART found.")
            return None
        
        # dtstart_obj.dt is the native datetime object, potentially with timezone from TZID
        original_dtstart_dt = dtstart_obj.dt 
        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Original DTSTART from VEVENT: {original_dtstart_dt.isoformat()} (tzinfo: {original_dtstart_dt.tzinfo})")
        
        dtstart_val_utc = _make_dt_aware(original_dtstart_dt) # Convert to UTC
        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): DTSTART converted to UTC: {dtstart_val_utc.isoformat()}")

        rrule_prop = event.get('rrule')
        
        next_occ_candidate = None

        if not rrule_prop: # ONE-OFF TASK
            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Is a ONE-OFF task.")
            # For one-off tasks, its only occurrence is its DTSTART.
            # Let's check if it's too far in the past based on a defined "catch-up window"
            catch_up_window = timedelta(minutes=5) # Allow catching up tasks missed by up to 5 minutes
            if dtstart_val_utc >= now_utc - catch_up_window:
                print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): One-off DTSTART {dtstart_val_utc.isoformat()} is within catch-up window from {now_utc.isoformat()}. Returning DTSTART.")
                next_occ_candidate = dtstart_val_utc
            else:
                print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): One-off DTSTART {dtstart_val_utc.isoformat()} is older than catch-up window from {now_utc.isoformat()}. Returning None.")
                next_occ_candidate = None # Explicitly None if too old
        else: # RECURRING TASK
            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Is a RECURRING task.")
            rrule_params = rrule_prop.to_dict()
            if 'FREQ' in rrule_params:
                rrule_params['FREQ'] = rrule_params['FREQ'].upper()
            for key, value in rrule_params.items():
                if isinstance(value, list) and len(value) == 1 and key not in ['BYDAY']:
                     if isinstance(value[0], int) and key.upper() not in ['BYSETPOS', 'BYMONTHDAY', 'BYYEARDAY', 'BYWEEKNO', 'BYHOUR', 'BYMINUTE', 'BYSECOND']:
                        rrule_params[key] = value[0]

            rule = rrule.rrule(dtstart=dtstart_val_utc, **rrule_params)

            # Find the first occurrence at or after (now_utc - a small grace period for just missed)
            # or if dtstart itself is the one
            grace_period_for_just_missed = timedelta(seconds=POLL_INTERVAL_SECONDS * 2)
            effective_search_start_utc = now_utc - grace_period_for_just_missed
            
            first_after_effective_start = rule.after(effective_search_start_utc, inc=True) # include if effective_search_start_utc is an occurrence
            
            if first_after_effective_start:
                print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): RRULE produced next occurrence candidate: {first_after_effective_start.isoformat()} (searching from {effective_search_start_utc.isoformat()})")
                next_occ_candidate = first_after_effective_start
            else:
                # This can happen if the recurrence has ended (e.g., due to COUNT or UNTIL)
                print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): RRULE did not produce a candidate after {effective_search_start_utc.isoformat()}.")
                next_occ_candidate = None
        
        # --- RDATE and EXDATE processing (can remain similar, ensure they use UTC candidate) ---
        # (Make sure next_occ_candidate is UTC before this section if it came from non-UTC source, but it should be)
        current_candidate_for_rdate_exdate = next_occ_candidate

        rdate_prop = event.get('rdates')
        if rdate_prop:
            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Processing RDATEs.")
            for rdate_list in rdate_prop:
                for rdate_val_obj in rdate_list.dts:
                    rdate_val = _make_dt_aware(rdate_val_obj.dt) # Ensure RDATE is UTC
                    # Consider RDATE if it's relevant (e.g., after effective search start for recurring or near DTSTART for one-off)
                    # and if it's earlier than the current RRULE-based candidate (or if no RRULE candidate)
                    if rdate_val >= effective_search_start_utc: # effective_search_start_utc from recurring or similar for one-off
                        if current_candidate_for_rdate_exdate is None or rdate_val < current_candidate_for_rdate_exdate:
                            current_candidate_for_rdate_exdate = rdate_val
                            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): RDATE updated candidate to {rdate_val.isoformat()}")
        
        if current_candidate_for_rdate_exdate:
            exdate_prop = event.get('exdates')
            if exdate_prop:
                print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Processing EXDATEs against candidate {current_candidate_for_rdate_exdate.isoformat()}.")
                is_excluded = False
                for exdate_list in exdate_prop:
                    for exdate_val_obj in exdate_list.dts:
                        exdate_val = _make_dt_aware(exdate_val_obj.dt) # Ensure EXDATE is UTC
                        if current_candidate_for_rdate_exdate.replace(microsecond=0) == exdate_val.replace(microsecond=0): # Compare without microseconds
                            is_excluded = True
                            print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Candidate {current_candidate_for_rdate_exdate.isoformat()} is EXCLUDED by {exdate_val.isoformat()}.")
                            break
                    if is_excluded: break
                
                if is_excluded:
                    # If excluded, and it was a recurring event, try to find the NEXT one after the exclusion
                    if rrule_prop: 
                        rule = rrule.rrule(dtstart=dtstart_val_utc, **rrule_params) # Re-init rule if needed
                        # Search for next occurrence strictly after the excluded datetime
                        next_after_exclusion = rule.after(current_candidate_for_rdate_exdate, inc=False)
                        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): After exclusion, RRULE gives next as {next_after_exclusion.isoformat() if next_after_exclusion else 'None'}.")
                        current_candidate_for_rdate_exdate = next_after_exclusion
                        # Re-check RDATEs if this new candidate from RRULE is later than an unexcluded RDATE
                        if rdate_prop and current_candidate_for_rdate_exdate:
                             for rdate_list_inner in rdate_prop:
                                for rdate_val_obj_inner in rdate_list_inner.dts:
                                    rdate_val_inner = _make_dt_aware(rdate_val_obj_inner.dt)
                                    # If this RDATE is after the EXDATE and before the new RRULE candidate
                                    if rdate_val_inner > exdate_val and rdate_val_inner < current_candidate_for_rdate_exdate:
                                        current_candidate_for_rdate_exdate = rdate_val_inner
                                        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): RDATE (post-EXDATE re-eval) updated candidate to {rdate_val_inner.isoformat()}")
                    else: # If it was a one-off or pure RDATE that got excluded
                        current_candidate_for_rdate_exdate = None 
                        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): Non-RRULE candidate was excluded, now None.")


        final_next_occ = current_candidate_for_rdate_exdate
        print(f"Scheduler DEBUG (calc_next_occ for task '{task_id_for_debug}'): FINAL candidate is {final_next_occ.isoformat() if final_next_occ else 'None'}.")
        return _make_dt_aware(final_next_occ) if final_next_occ else None # Ensure final result is UTC aware

    except Exception as e:
        print(f"Scheduler Error (calc_next_occ for task '{task_id_for_debug}'): Could not parse VEVENT or calculate: {e}\nVEVENT: {vevent_str[:100]}...")
        return None


def inject_prompt_via_api(conversation_id: str, user_prompt: str, task_id: str) -> bool:
    payload = {
        "conversation_id": conversation_id,
        "user_prompt": user_prompt,
        "task_id": task_id 
    }
    try:
        print(f"Scheduler INFO (inject_prompt): Attempting task_id {task_id}, conv_id {conversation_id}...")
        response = requests.post(MAIN_APP_INJECTION_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200:
            print(f"Scheduler INFO (inject_prompt): Success task_id {task_id}. Response: {response.json()}")
            return True
        else:
            print(f"Scheduler ERROR (inject_prompt): Failed task_id {task_id}. Status: {response.status_code}, Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Scheduler ERROR (inject_prompt): HTTP request failed task_id {task_id}: {e}")
        return False

def process_scheduled_tasks():
    print(f"\nScheduler INFO (process_tasks): Cycle start at {datetime.now(timezone.utc).isoformat()}")
    tasks = _load_tasks_for_scheduler()
    now_utc = datetime.now(timezone.utc)

    if not tasks:
        print("Scheduler INFO (process_tasks): No tasks found in JSON file.")
        return

    print(f"Scheduler INFO (process_tasks): Processing {len(tasks)} tasks. Current time (UTC): {now_utc.isoformat()}")

    for task_index, task in enumerate(tasks):
        task_id = task.get("id", f"unknown_id_at_index_{task_index}")
        print(f"\nScheduler INFO (process_tasks): Evaluating task {task_id} (index {task_index})")
        
        is_one_off = "RRULE" not in task.get("schedule_vevent", "").upper() and "RDATE" not in task.get("schedule_vevent", "").upper()
        if is_one_off and task_id in FIRED_ONCE_TASK_IDS:
            print(f"Scheduler INFO (process_tasks): Task {task_id} is one-off and already in FIRED_ONCE_TASK_IDS. Skipping.")
            continue
            
        vevent_str = task.get("schedule_vevent")
        if not vevent_str:
            print(f"Scheduler WARNING (process_tasks): Task {task_id} has no schedule_vevent. Skipping.")
            continue

        next_occurrence_utc = calculate_next_occurrence(task_id, vevent_str, now_utc)

        if next_occurrence_utc:
            print(f"Scheduler INFO (process_tasks): Task {task_id} - Calculated next_occurrence (UTC): {next_occurrence_utc.isoformat()}")
            # Condition for DUE: next occurrence is in the past, present, or very near future (within one poll interval)
            # This ensures we catch tasks that might have been scheduled between polls.
            # The "+ timedelta(seconds=1)" is to make sure if now_utc is *exactly* next_occurrence_utc, it's caught.
            if next_occurrence_utc <= now_utc + timedelta(seconds=POLL_INTERVAL_SECONDS / 2):
                conversation_id = task.get("conversation_id")
                user_prompt = task.get("user_prompt")

                if not conversation_id or not user_prompt:
                    print(f"Scheduler ERROR (process_tasks): Task {task_id} is DUE but missing conversation_id or user_prompt.")
                    continue
                
                print(f"Scheduler ACTION (process_tasks): >>> Task DUE: ID {task_id}, ConvID: {conversation_id}, NextRunUTC: {next_occurrence_utc.isoformat()}, Prompt: '{user_prompt[:50]}...'")
                if inject_prompt_via_api(conversation_id, user_prompt, task_id):
                    if is_one_off: # Check if it's a one-off task again
                        FIRED_ONCE_TASK_IDS.add(task_id)
                        print(f"Scheduler INFO (process_tasks): Task {task_id} (one-off) successfully injected and added to FIRED_ONCE_TASK_IDS.")
                    # For recurring tasks, they will just be evaluated again next time for their next occurrence.
                else:
                    print(f"Scheduler WARNING (process_tasks): Failed to inject prompt for DUE task {task_id}. Will retry next cycle if applicable.")
            else:
                print(f"Scheduler INFO (process_tasks): Task {task_id} - Next occurrence {next_occurrence_utc.isoformat()} is not due yet (now_utc: {now_utc.isoformat()}, due_if_before: {(now_utc + timedelta(seconds=POLL_INTERVAL_SECONDS / 2)).isoformat()}).")
        else:
            print(f"Scheduler INFO (process_tasks): Task {task_id} - No upcoming calculable occurrence found.")


if __name__ == "__main__":
    print("Scheduler process started.")
    print(f"Polling interval: {POLL_INTERVAL_SECONDS} seconds.")
    print(f"Main application injection URL: {MAIN_APP_INJECTION_URL}")
    
    while True:
        try:
            process_scheduled_tasks()
        except Exception as e:
            print(f"Scheduler CRITICAL ERROR: Unhandled exception in main loop: {e}") # Changed to CRITICAL
        print(f"Scheduler INFO: --- Cycle complete. Sleeping for {POLL_INTERVAL_SECONDS} seconds. ---")
        time.sleep(POLL_INTERVAL_SECONDS)