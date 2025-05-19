# Chatty - AI Powered Assistant

Chatty is a web-based chat application featuring an interactive AI assistant. It utilizes a Python (FastAPI) backend and a JavaScript frontend to deliver a seamless user experience. The AI is powered by Google's Gemini model and can perform various tasks including controlling smart home devices, managing your Google Calendar, interacting with the local file system, and performing web searches.

## Key Features

*   **Interactive Chat:** Communicate with the AI assistant "Chatty" using text or voice input.
*   **Smart Light Control:** Manage Kasa smart lights (toggle on/off, adjust brightness, set colors).
*   **Google Calendar Integration:** List upcoming events, create new events, and delete existing events from your Google Calendar.
*   **File System Operations:** The agent can list files, read their content, and write to files within its designated environment.
*   **Persistent Memory:** "Chatty" can remember details and preferences across conversation sessions.
*   **Scheduled Tasks:** "Chatty" can remember to perform actions or remind you of things at a specified time. You can create, view, and cancel these scheduled tasks.
*   **Google Search:** The agent can perform Google searches to fetch real-time information and answer queries.
*   **Real-time Interaction:** Utilizes WebSockets for instant, bidirectional communication between the user interface and the backend agent.
*   **Voice-Enabled:** Supports voice input for commands and queries, and can respond with voice output.

## Technical Stack

**Backend:**
*   Python 3.x
*   FastAPI: For the web framework and WebSocket handling.
*   Google Generative AI (Gemini): The core AI model powering the assistant (e.g., models like `gemini-1.5-flash`).
*   `python-kasa`: For controlling Kasa smart home devices.
*   Google Calendar API: For calendar integration.
*   `scheduler.py`: Manages scheduled tasks, triggering agent actions at specified times via the task injection API.
*   Uvicorn: ASGI server for FastAPI.
*   Utilizes "Aoede" prebuilt voice for synthesized voice responses.

**Frontend:**
*   HTML5
*   CSS3
*   Vanilla JavaScript: For client-side logic, DOM manipulation, and WebSocket communication.
*   Web Audio API (AudioWorklets): For custom audio processing (recording and playback).

**Key Python Libraries Used:**
*   `google-genai`
*   `google-api-python-client`
*   `google-auth-httplib2`
*   `google-auth-oauthlib`
*   `python-kasa`
*   `fastapi`
*   `websockets` (implicitly used by FastAPI)
*   `uvicorn`
*   `python-dotenv`

**Communication Protocol:**
*   WebSockets: For real-time, full-duplex communication between the client and server.

## Project Structure

Here's a brief overview of the key files and directories within the project:

*   **`main.py`**: The main entry point for the backend application. It initializes FastAPI, handles WebSocket connections, and manages agent sessions.
*   **`light_agent/`**: This directory contains the core logic for the AI assistant.
    *   **`agent.py`**: Defines the "Chatty" agent, including its persona, instructions, and the tools it can use (light control, calendar management, file operations, memory, web search, and task scheduling). It also initializes the Gemini client and configures the agent's capabilities.
    *   **`fileTools.py`**: Provides utility functions for the agent to interact with the file system (listing files, reading content, writing content).
    *   **`memoryTools.py`**: Contains functions that allow the agent to store and retrieve information, enabling persistent memory across sessions.
    *   **`taskTools.py`**: Provides functions for creating, listing, and deleting scheduled tasks for the agent.
*   **`scheduler.py`**: A script that runs periodically to check for scheduled tasks (defined in `scheduled_tasks.json`) and uses an API endpoint (`/api/inject-task-prompt` in `main.py`) to inject the task prompt into the relevant agent session at the scheduled time.
*   **`static/`**: This directory holds all the frontend assets.
    *   **`index.html`**: The main HTML file for the chat interface.
    *   **`js/app.js`**: The primary JavaScript file for the frontend. It manages client-side logic, establishes and handles WebSocket communication with the backend, updates the chat UI, and integrates audio input/output.
    *   **`js/audio-player.js`**: An AudioWorklet processor for playing back PCM audio streams received from the agent.
    *   **`js/audio-recorder.js`**: An AudioWorklet processor for capturing PCM audio from the user's microphone.
    *   **`images/favicon.ico`**: The favicon for the application.
*   **`.env-example`**: A template file for setting up environment variables. You should copy this to a `.env` file and populate it with your actual credentials.
*   **`credentials.json`**: (Not included in the repository for security) This file is required for Google Calendar API access. You need to obtain it from the Google Cloud Console.
*   **`token.json`**: (Not included in the repository) This file is automatically generated/updated after successful user authentication for Google Calendar access. It stores the user's access and refresh tokens.
*   **`scheduled_tasks.json`**: (Not included in the repository, generated at runtime) Stores the details of tasks scheduled by the agent.
*   **`LICENSE`**: Contains the license information for the project.
*   **`README.md`**: (This file) Provides an overview of the project, setup instructions, and other relevant details.

## Setup and Installation

Follow these steps to set up and run the Chatty application on your local machine.

**1. Clone the Repository:**

```bash
git clone <repository-url> # Replace <repository-url> with the actual URL
cd <repository-directory>
```

**2. Backend Setup:**

   a.  **Create and Activate a Python Virtual Environment:**
        It's highly recommended to use a virtual environment to manage project dependencies.

        ```bash
        python -m venv venv
        # On Windows
        venv\Scripts\activate
        # On macOS/Linux
        source venv/bin/activate
        ```

   b.  **Install Python Dependencies:**
        Install all required Python packages using the `requirements.txt` file.

        ```bash
        pip install -r requirements.txt
        ```

   c.  **Set Up Environment Variables:**
        Copy the `.env-example` file to a new file named `.env`.

        ```bash
        cp .env-example .env
        ```
        Open the `.env` file and add your Gemini API Key:

        ```env
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        ```
        Replace `"YOUR_GEMINI_API_KEY"` with your actual API key.

   d.  **Google Calendar API Setup:**
        *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
        *   Create a new project or select an existing one.
        *   Enable the "Google Calendar API" for your project.
        *   Create OAuth 2.0 credentials for a "Desktop application".
        *   Download the credentials JSON file. Rename it to `credentials.json` and place it in the root directory of this project.
        *   **Important:** The `credentials.json` file should NOT be committed to version control if this is a public repository.
        *   The first time you run the application and try to use a calendar feature, it will open a browser window for you to authorize access. After successful authorization, a `token.json` file will be created in the root directory. This file stores your OAuth tokens and should also not be committed.

   e.  **Kasa Smart Light Configuration:**
        *   Ensure your Kasa smart lights are connected to the same Wi-Fi network as the machine running the backend server.
        *   The IP addresses for the Kasa devices are currently hardcoded in `light_agent/agent.py` (variables `FIRST_IP_ADDRESS` and `SECOND_IP_ADDRESS`). You may need to update these with the actual IP addresses of your devices. You can usually find these in your router's DHCP client list or using the Kasa mobile app.

**3. Running the Application:**

   Once the backend is set up, you can start the FastAPI application using Uvicorn:

   ```bash
   uvicorn main:app --reload
   ```
   *   `--reload` enables auto-reloading when code changes, which is useful for development.
   *   The application will typically be available at `http://120.0.0.1:8000`.

## Usage

1.  **Open the Application:**
    *   Once the backend server is running (e.g., at `http://127.0.0.1:8000`), open this URL in your web browser.

2.  **Interacting with Chatty:**
    *   **Text Input:** Type your message in the input field at the bottom of the chat window and press Enter or click the "Send" button.
    *   **Voice Input:** Click the "Voice Mode" button to enable voice input. The assistant will indicate it's listening. Speak your command or query. The assistant will process the audio and respond. Click the button again (or it might automatically revert after processing) to switch back to text input or await further voice commands.

3.  **Example Commands/Interactions:**

    *   **General Conversation:**
        *   "Hi, how are you today?"
        *   "Tell me a joke."
        *   "What's the weather like in London?" (Uses Google Search)

    *   **Smart Light Control:**
        *   "Turn on the lights."
        *   "Turn off the lights."
        *   "Set the light brightness to 50 percent."
        *   "Change the lights to blue."
        *   "What's the current state of the lights?"

    *   **Google Calendar:**
        *   "What's on my calendar today?"
        *   "Create a calendar event: Team meeting tomorrow at 10 AM EST for 1 hour titled 'Project Sync'."
        *   "Delete the event 'Project Sync' from my calendar." (You might need to list events first to get an exact ID or confirm details if the agent asks).

    *   **File System (if configured and permitted by the agent's tools):**
        *   "List files in the current directory."
        *   "Read the content of 'config.txt'." (Note: The agent's file access is sandboxed/restricted by its programming).

    *   **Memory:**
        *   "My name is Alex."
        *   (Later) "What's my name?"
        *   "Remember that I prefer the lights to be dim in the evening."

    *   **Scheduled Tasks:**
        *   "Remind me to call John tomorrow at 10 AM."
        *   "What tasks do I have scheduled?"
        *   "Can you cancel my reminder to call John?"

    The agent is designed to be conversational. Try different phrasings and see how it responds!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contributing

Contributions are welcome! If you'd like to contribute to Chatty, please follow these general guidelines:

1.  **Fork the Repository:** Create your own fork of the project.
2.  **Create a Branch:** Make your changes in a dedicated branch in your forked repository.
    ```bash
    git checkout -b my-feature-branch
    ```
3.  **Make Changes:** Implement your feature or bug fix.
4.  **Test Your Changes:** Ensure your changes work as expected and do not break existing functionality.
5.  **Commit Your Changes:** Write clear and concise commit messages.
    ```bash
    git commit -m "feat: Add new feature"
    ```
6.  **Push to Your Fork:**
    ```bash
    git push origin my-feature-branch
    ```
7.  **Submit a Pull Request:** Open a pull request from your feature branch to the main branch of the original repository. Provide a clear description of your changes.

We'll review your pull request and merge it if it aligns with the project's goals.
