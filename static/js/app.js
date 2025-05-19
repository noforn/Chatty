const sessionId = Math.random().toString().substring(10);
const ws_url =
  "ws://" + window.location.host + "/ws/" + sessionId;
let websocket = null;
let is_audio = false;

// Get DOM elements
const messageForm = document.getElementById("messageForm");
const messageInput = document.getElementById("message");
const messagesDiv = document.getElementById("messages"); // This is your main messages container
let currentAIMessageElement = null; // To hold the current AI message bubble for streaming

// --- NEW: Get the visualizer element ---
const voiceVisualizer = document.getElementById("voice-mode-visualizer");

// --- NEW: Function to update visualizer visibility ---
function updateVoiceVisualizerState() {
  if (!voiceVisualizer) return;

  // Show if in audio mode AND messagesDiv essentially empty or has only initial system messages
  let showVisualizer = false;
  if (is_audio) {
    if (messagesDiv.children.length === 0) { // No messages at all (besides the visualizer itself if it's a direct child and we filter it out)
        showVisualizer = true;
    } else if (messagesDiv.children.length === 1 || (messagesDiv.children.length === 2 && messagesDiv.contains(voiceVisualizer))) {
        // Check if the only message(s) are initial system status messages or the visualizer div
        let nonVisualizerChildren = 0;
        let isInitialSystemMessagePresent = false;
        for (let i = 0; i < messagesDiv.children.length; i++) {
            if (messagesDiv.children[i].id !== 'voice-mode-visualizer') {
                nonVisualizerChildren++;
                if (messagesDiv.children[i].classList.contains("system")) {
                    const text = messagesDiv.children[i].textContent.toLowerCase();
                    if (text.includes("stream started") || text.includes("voice mode active")) {
                        isInitialSystemMessagePresent = true;
                    } else {
                        isInitialSystemMessagePresent = false; // It's a regular AI response
                        break;
                    }
                } else {
                     isInitialSystemMessagePresent = false; // It's a user message
                     break;
                }
            }
        }
        if (nonVisualizerChildren === 0 || (nonVisualizerChildren === 1 && isInitialSystemMessagePresent)) {
            showVisualizer = true;
        }
    }
  }

  if (showVisualizer) {
    console.log("DEBUG: Adding .active class to visualizer");
    voiceVisualizer.classList.add("active");
  } else {
    console.log("DEBUG: Removing .active class from visualizer");
    voiceVisualizer.classList.remove("active");
  }
}

// Function to create and append a styled message bubble
function createMessageBubble(text, type) {
  const messageElement = document.createElement("div");
  messageElement.classList.add("message-item", type);
  messageElement.textContent = text;
  
  if (messagesDiv) {
    // If the visualizer is the only child, remove it or insert before it
    if (voiceVisualizer && messagesDiv.contains(voiceVisualizer) && messagesDiv.firstChild === voiceVisualizer && messagesDiv.children.length === 1) {
        messagesDiv.insertBefore(messageElement, voiceVisualizer.nextSibling); // Insert after visualizer if it's first
    } else {
        messagesDiv.appendChild(messageElement);
    }
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  } else {
    console.error("messagesDiv is not found!");
  }
  
  updateVoiceVisualizerState(); // Update visualizer when a new message is added
  return messageElement;
}

// WebSocket handlers
function connectWebsocket() {
  websocket = new WebSocket(ws_url + "?is_audio=" + is_audio);

  websocket.onopen = function () {
    console.log("WebSocket connection opened.");
  
    const visualizerWasPresentAndIsChild = voiceVisualizer && messagesDiv.contains(voiceVisualizer);
    messagesDiv.innerHTML = ""; // Clear all previous messages
  
    if (visualizerWasPresentAndIsChild && voiceVisualizer) { // If it was there and got wiped by innerHTML
        messagesDiv.appendChild(voiceVisualizer); // Re-append it.
    }
  
    createMessageBubble("Stream started!", "system"); 
  
    document.getElementById("sendButton").disabled = false;
    addSubmitHandler();
    updateVoiceVisualizerState(); 
  };

  websocket.onmessage = function (event) {
    const message_from_server = JSON.parse(event.data);
    console.log("[AGENT TO CLIENT] ", message_from_server);

    if (message_from_server.turn_complete === true) {
      currentAIMessageElement = null;
      updateVoiceVisualizerState(); // Update in case the state should change
      return;
    }

    let textChunkToDisplay = null;
    if (message_from_server.mime_type == "text/plain" && typeof message_from_server.data === 'string') {
        textChunkToDisplay = message_from_server.data;
    } else if (typeof message_from_server.transcript_chunk === 'string') {
        textChunkToDisplay = message_from_server.transcript_chunk;
    }

    if (textChunkToDisplay !== null) {
        if (!currentAIMessageElement) {
            currentAIMessageElement = createMessageBubble(textChunkToDisplay, "system");
        } else {
            currentAIMessageElement.textContent += textChunkToDisplay;
            if (messagesDiv && currentAIMessageElement.parentNode === messagesDiv) {
                 messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }
        updateVoiceVisualizerState(); // Hide visualizer when text appears
    }

    if (message_from_server.mime_type == "audio/pcm" && audioPlayerNode && message_from_server.data) {
      audioPlayerNode.port.postMessage(base64ToArray(message_from_server.data));
      // updateVoiceVisualizerState(); // Called if textChunkToDisplay was also present
    }
  };

  websocket.onclose = function (event) {
    console.log("WebSocket connection closed.", event.code, event.reason);
    document.getElementById("sendButton").disabled = true;
    
    if (voiceVisualizer) { // Explicitly hide visualizer
        voiceVisualizer.classList.remove("active");
    }
    // Avoid showing "Stream disconnected" if it was a deliberate close for mode change
    // and if app.js will immediately try to reconnect with new params.
    // However, the current logic for mode change in startAudioButton handles the reconnect.
    createMessageBubble("Stream disconnected. Reconnecting...", "system");
    currentAIMessageElement = null;

    setTimeout(function () {
      console.log("Reconnecting...");
      connectWebsocket();
    }, 5000);
  };

  websocket.onerror = function (e) {
    console.log("WebSocket error: ", e);
    currentAIMessageElement = null;
    if (voiceVisualizer) { // Hide on error too
        voiceVisualizer.classList.remove("active");
    }
    updateVoiceVisualizerState();
  };
}
connectWebsocket();

// Add submit handler to the form
function addSubmitHandler() {
  messageForm.onsubmit = function (e) {
    e.preventDefault();
    const messageText = messageInput.value.trim();
    if (messageText) {
      createMessageBubble(messageText, "user"); // This will also call updateVoiceVisualizerState
      messageInput.value = "";
      sendMessage({
        mime_type: "text/plain",
        data: messageText,
      });
      console.log("[CLIENT TO AGENT] " + messageText);
    }
    return false;
  };
}

// Send a message to the server as a JSON string
function sendMessage(message) {
  if (websocket && websocket.readyState == WebSocket.OPEN) {
    const messageJson = JSON.stringify(message);
    websocket.send(messageJson);
  }
}

// Decode Base64 data to Array
function base64ToArray(base64) {
  const binaryString = window.atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

/**
 * Audio handling
 */

let audioPlayerNode;
let audioPlayerContext;
let audioRecorderNode;
let audioRecorderContext;
let micStream;

// Import the audio worklets
// Ensure these paths are correct relative to your app.js if it's in a /static/js/ folder
// If app.js is in the root, then './audio-player.js' is fine.
// If app.js is in /static/js/, and audio-player.js is also in /static/js/, then './audio-player.js' is correct.
import { startAudioPlayerWorklet } from "./audio-player.js";
import { startAudioRecorderWorklet } from "./audio-recorder.js";

// Start audio
function startAudio() {
  // Start audio output
  startAudioPlayerWorklet().then(([node, ctx]) => {
    audioPlayerNode = node;
    audioPlayerContext = ctx;
  });
  // Start audio input
  startAudioRecorderWorklet(audioRecorderHandler).then(
    ([node, ctx, stream]) => {
      audioRecorderNode = node;
      audioRecorderContext = ctx;
      micStream = stream;
    }
  );
}

// Start the audio only when the user clicked the button
startAudioButton.addEventListener("click", () => {
  startAudioButton.disabled = true;
  startAudio();
  is_audio = true; // Set this flag

  // messagesDiv.innerHTML = ""; // Optionally clear messages to show animation cleanly
  createMessageBubble("Listening...", "system"); // Optional: Notify user
  
  // Reconnect WebSocket with the new is_audio state
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.onclose = function() {}; // Temporarily disable default onclose to prevent immediate reconnect loop by old handler
    websocket.close(1000, "Mode change to audio"); // Close normally
    connectWebsocket(); // Reconnect immediately with new is_audio state
  } else {
    connectWebsocket(); // Or connect if not already open
  }
  updateVoiceVisualizerState(); // Ensure visualizer is shown if conditions are met
});

// Audio recorder handler
function audioRecorderHandler(pcmData) {
  sendMessage({
    mime_type: "audio/pcm",
    data: arrayBufferToBase64(pcmData),
  });
  console.log("[CLIENT TO AGENT] sent %s bytes", pcmData.byteLength);
}

// Encode an array buffer with Base64
function arrayBufferToBase64(buffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}