import os
import requests
import json
import subprocess
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from pdb import set_trace as stop

from smolagents import tool
from pylint.lint import Run
from pylint.reporters.text import TextReporter

# --- Configuration ---
DAGS_DIR = Path(os.environ.get("AIRFLOW_DAGS", "/home/dsamarka/airflow/dags"))
DAG_STORAGE_PATH = DAGS_DIR / "generated_nasdaq.py"

# It's good practice to check for essential configs at the start
AIRFLOW_API_BASE_URL = os.environ.get("AIRFLOW_API_BASE_URL", "http://localhost:8080/api/v2")
AIRFLOW_ACCESS_TOKEN = os.environ.get("AIRFLOW_ACCESS_TOKEN")


def _make_airflow_api_request(method: str, endpoint: str, payload: Optional[dict] = None) -> dict:
    """
    A helper function to centralize requests to the Airflow REST API.

    Handles URL construction, authentication, and error handling for API calls.

    Args:
        method: The HTTP method ("GET", "POST", etc.).
        endpoint: The API endpoint (e.g., "dags/my_dag/dagRuns").
        payload: Optional dictionary for the JSON request body.

    Returns:
        A dictionary parsed from the API's JSON response.

    Raises:
        ValueError: If the AIRFLOW_ACCESS_TOKEN is not configured.
        requests.exceptions.HTTPError: For HTTP-related errors.
        requests.exceptions.RequestException: For network-related issues.
    """
    if not AIRFLOW_ACCESS_TOKEN:
        raise ValueError("AIRFLOW_ACCESS_TOKEN environment variable is not set.")

    url = f"{AIRFLOW_API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {AIRFLOW_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    response = requests.request(method, url, headers=headers, data=json.dumps(payload) if payload else None)
    response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
    return response.json()


@tool
def pipelineRescanTool() -> str:
    """
    Rescans Airflow DAGs.

    This tool simulates how Airflow's Scheduler discovers and parses DAG files.
    It executes a command to load the DAG bag in a separate process, ensuring
    the environment is clean and dependencies are isolated. This helps catch
    syntax errors or import issues before deployment.

    Returns:
        A string "OK" if the DAG file is parsed successfully. Otherwise, it
        returns "NOK" with the stderr from the command, which contains the
        error traceback.
    """
    print(f"Rescan DAG files '{DAG_STORAGE_PATH}' using Airflow's DagBag...")
    if not DAG_STORAGE_PATH.exists():
        return f"NOK: The DAG file does not exist at '{DAG_STORAGE_PATH}'"

    # Set the dags_folder for the subprocess environment
    env = os.environ.copy()
    env["AIRFLOW__CORE__DAGS_FOLDER"] = str(DAG_STORAGE_PATH.parent)
    command = [
        "python3", "-c",
        "from airflow.models import DagBag; DagBag(include_examples=False, read_dags_from_db=False)"
    ]

    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            check=True  # Let subprocess raise an exception on non-zero exit codes
        )
        print("--> OK: DAG file successfully loaded by DagBag without errors.")
        return "OK"
    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout
        error_message = f"NOK: Failed to load DAG file with DagBag.\n--- Error ---\n{error_output.strip()}"
        print(f"--> Validation Failed.\n{error_message}")
        return error_message
    except FileNotFoundError:
        # This catches the case where 'python3' is not found
        return "NOK: 'python3' command not found. Please ensure Python 3 is in your system's PATH."
    except Exception as e:
        return f"NOK: An unexpected error occurred during validation: {e}"


@tool
def validatePipelineTool() -> str:
    """
    Analyzes a Python pipeline file

    Returns:
        Result of the analysis
    """
    command = ["airflow", "dags", "list-import-errors", "-B", "dags-folder"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        reply_from_command = result.stdout + " " + result.stderr
    except subprocess.CalledProcessError as e:
        reply_from_command = f"Command failed with error:\n{e.stderr}"

    return reply_from_command

@tool
def testPipelineTool(dag_id: str) -> str:
    """
    Test a Python pipeline file using pylint to check for fatal errors.

    Args:
        dag_id: The unique identifier of the DAG to test.

    Returns:
        Result of the execution via DagRun
    """
    command = ["airflow", "dags", "test", dag_id]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        reply_from_command = result.stdout + " " + result.stderr
    except subprocess.CalledProcessError as e:
        reply_from_command = f"Command failed with error:\n{e.stderr}"

    return reply_from_command

@tool
def pipelineTriggerTool(dag_id: str) -> str:
    """
    Triggers a new run for a specified DAG using the Airflow REST API.

    A unique `dag_run_id` is generated using a timestamp to ensure each run is distinct.

    Args:
        dag_id: The unique identifier of the DAG to trigger.

    Returns:
        A success message with the new run's ID and state, or an error message.
    """
    print(f"Attempting to trigger DAG '{dag_id}'...")
    try:
        payload = {
            "dag_run_id": f"run_{datetime.utcnow().isoformat().replace('-', '_').replace(':', '_').replace('.', '_')}",
            "logical_date": datetime.utcnow().isoformat() + "Z",
            "conf": {},
        }
        data = _make_airflow_api_request("POST", f"dags/{dag_id}/dagRuns", payload)
        run_id = data.get('dag_run_id', 'N/A')
        state = data.get('state', 'N/A')
        success_message = f"Successfully triggered DAG '{dag_id}'. Run ID: '{run_id}', State: {state}."
        print(f"--> {success_message}")
        return success_message
    except (requests.exceptions.RequestException, ValueError) as e:
        error_message = f"Failed to trigger DAG '{dag_id}'. Reason: {e}"
        print(f"--> {error_message}")
        return error_message


@tool
def pipelineStatusTool(dag_id: str, run_id: str) -> str:
    """
    Retrieves the status of a specific DAG run from the Airflow REST API.

    Args:
        dag_id: The ID of the DAG to check.
        run_id: The ID of the specific DAG run to get the status for.

    Returns:
        The state of the DAG run (e.g., 'running', 'success'), or an error message.
    """
    print(f"Fetching status for DAG '{dag_id}', run '{run_id}'...")
    try:
        endpoint = f"dags/{dag_id}/dagRuns/{run_id}"
        data = _make_airflow_api_request("GET", endpoint)
        state = data.get('state', "Unknown")
        print(f"--> The state of the DAG run is: {state}")
        return state
    except (requests.exceptions.RequestException, ValueError) as e:
        error_message = f"Failed to get status for DAG '{dag_id}'. Reason: {e}"
        print(f"--> {error_message}")
        return error_message


@tool
def storePipelineTool(content: str) -> str:
    """
    Saves Python code content to the DAG storage file path.

    This tool persists a generated DAG file to a location where Airflow can
    discover it. It ensures the target directory exists before writing the file.

    Args:
        content: A string containing the Python code to be saved.

    Returns:
        A string indicating the success or failure of the file operation.
    """
    print(f"Saving content to {DAG_STORAGE_PATH}...")
    try:
        # Ensure the parent directory exists
        DAG_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DAG_STORAGE_PATH.write_text(content, encoding='utf-8')
        success_message = f"Successfully saved code to {DAG_STORAGE_PATH}"
        print(f"--> {success_message}")
        return success_message
    except (IOError, OSError) as e:
        error_message = f"Error writing file to {DAG_STORAGE_PATH}: {e}"
        print(f"--> {error_message}")
        return error_message
