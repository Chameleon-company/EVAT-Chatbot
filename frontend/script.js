const chat = document.getElementById("chat");
const form = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const typingIndicator = document.getElementById("typing-indicator");
const clearBtn = document.getElementById("clear-btn");

let userLocation = null;

// Restore chat from localStorage
window.onload = async () => {
  const stored = localStorage.getItem("chatHistory");
  if (stored) chat.innerHTML = stored;

  addMessage("Hi! I'm EVAT. Getting your location...", "bot");

  // Try to get user location and send it to Rasa
  try {
    const loc = await getUserLocation();
    userLocation = {
      lat: loc.coords.latitude,
      lng: loc.coords.longitude  // Changed from 'lon' to 'lng' to match Rasa
    };

    // Automatically send location to Rasa to trigger the menu
    await sendLocationToRasa();

  } catch (error) {
    // Location failed, show fallback message
    addMessage("Location access denied. Please type your suburb name (e.g., 'Richmond') to continue.", "bot");
  }
};

function addMessage(text, sender = "bot") {
  // Create the message container
  const msg = document.createElement("div");
  msg.classList.add("message", sender);
  msg.textContent = text;

  // Create the timestamp
  const timestamp = document.createElement("div");
  timestamp.className = "timestamp";
  timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // Append the message and timestamp to the chat
  chat.appendChild(msg);
  chat.appendChild(timestamp);

  // Manually set a timeout to ensure the DOM is updated before scrolling
  setTimeout(() => {
    // Ensure that we scroll the chat container and not just the messages
    const chatContainer = document.getElementById("chat-container");

    // Log to ensure we are selecting the correct element
    console.log("chatContainer scrollHeight: ", chatContainer.scrollHeight);
    console.log("chatContainer scrollTop: ", chatContainer.scrollTop);
    console.log("chatContainer clientHeight: ", chatContainer.clientHeight);

    // Scroll the chat container to the bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }, 0);

  // Save chat history to localStorage
  localStorage.setItem("chatHistory", chat.innerHTML);
}


function addDirectionsCard(payload) {
  const container = document.createElement("div");
  container.classList.add("message", "bot");
  container.innerHTML = `
    <div><strong>🗺️ Directions</strong></div>
    <div>${payload.origin} → ${payload.destination}</div>
    <div>Distance: ${payload.distance_km != null ? payload.distance_km.toFixed(1) + ' km' : '—'} | ETA: ${payload.eta_min != null ? Math.round(payload.eta_min) + ' min' : '—'}${payload.delay_min ? ` (+${Math.round(payload.delay_min)} min traffic)` : ''}</div>
    ${payload.maps_url ? `<div style="margin-top:6px"><a href="${payload.maps_url}" target="_blank" rel="noopener">Open in Google Maps</a></div>` : ''}
  `;
  chat.appendChild(container);

  // instruction but not done
  const steps = Array.isArray(payload.instructions)
    ? payload.instructions
    : (typeof payload.instructions === 'string' ? [payload.instructions] : []);
  if (Array.isArray(steps) && steps.length) {
    const list = document.createElement('ol');
    list.style.margin = '6px 0 0 18px';
    steps.slice(0, 8).forEach(step => {
      const li = document.createElement('li');
      li.textContent = step;
      list.appendChild(li);
    });
    chat.appendChild(list);
  }

  // Scroll and persist
  const timestamp = document.createElement("div");
  timestamp.className = "timestamp";
  timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  chat.appendChild(timestamp);
  const chatContainer = document.getElementById("chat-container");
  if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
  localStorage.setItem("chatHistory", chat.innerHTML);
}

function addTrafficCard(payload) {
  const container = document.createElement("div");
  container.classList.add("message", "bot");
  const speedText = (payload.current_speed_kmh != null && payload.free_flow_speed_kmh != null)
    ? ` | Speed: ${Math.round(payload.current_speed_kmh)} km/h (free-flow ${Math.round(payload.free_flow_speed_kmh)} km/h)`
    : '';
  const congestionText = payload.congestion_level != null ? ` | Level ${payload.congestion_level}` : '';
  container.innerHTML = `
    <div><strong>🚦 Traffic</strong></div>
    <div>${payload.origin} → ${payload.destination}</div>
    <div>Status: ${payload.status || 'Available'}${congestionText}${speedText}${payload.delay_min != null ? ` | Delay: ${Math.round(payload.delay_min)} min` : ''}</div>
  `;
  chat.appendChild(container);

  const timestamp = document.createElement("div");
  timestamp.className = "timestamp";
  timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  chat.appendChild(timestamp);
  const chatContainer = document.getElementById("chat-container");
  if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
  localStorage.setItem("chatHistory", chat.innerHTML);
}

function handleRasaResponse(messages) {
  messages.forEach((msg) => {
    // Standard text
    if (msg.text) addMessage(msg.text, "bot");

    // Custom JSON payloads (Rasa REST channel: "custom" field)
    const payload = msg.custom || msg.json_message || null;
    if (!payload || typeof payload !== 'object') return;

    if (payload.type === 'directions') {
      addDirectionsCard(payload);
    } else if (payload.type === 'traffic') {
      addTrafficCard(payload);
    }
  });
}



async function getUserLocation() {
  return new Promise((resolve, reject) => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(resolve, reject);
    } else {
      reject(new Error("Geolocation not supported."));
    }
  });
}

async function sendLocationToRasa() {
  try {
    const payload = {
      sender: "user",
      message: "hello",  // Send a greeting to trigger the menu
      metadata: userLocation
    };

    const response = await fetch("http://localhost:5005/webhooks/rest/webhook", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (data.length > 0) {
      handleRasaResponse(data);
    }
  } catch (err) {
    console.error("Error sending location to Rasa:", err);
  }
}

async function sendMessage(message) {
  typingIndicator.classList.remove("hidden");

  try {
    const payload = {
      sender: "user",
      message,
      metadata: userLocation || {}
    };

    const response = await fetch("http://localhost:5005/webhooks/rest/webhook", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (data.length === 0) {
      addMessage("Sorry, I didn’t understand that.", "bot");
    } else {
      handleRasaResponse(data);
    }
  } catch (err) {
    addMessage("Server error. Please try again.", "bot");
  } finally {
    typingIndicator.classList.add("hidden");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;

  addMessage(message, "user");
  userInput.value = "";
  userInput.rows = 1;

  await sendMessage(message);
});

userInput.addEventListener("input", () => {
  userInput.rows = Math.min(5, Math.ceil(userInput.scrollHeight / 24));
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

clearBtn.addEventListener("click", () => {
  if (confirm("Clear all chat messages?")) {
    chat.innerHTML = "";
    localStorage.removeItem("chatHistory");
    addMessage("Chat cleared. How can I help you now?", "bot");
  }
});
