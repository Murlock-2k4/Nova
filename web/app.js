const commandForm = document.getElementById("command-form");
const commandInput = document.getElementById("command-input");
const sendButton = document.getElementById("send-button");

const messagesContainer = document.getElementById("messages");
const clearButton = document.getElementById("clear-button");

const novaOrb = document.getElementById("nova-orb");
const orbLabel = document.getElementById("orb-label");
const statusTitle = document.getElementById("status-title");

const connectionDot = document.getElementById("connection-dot");
const connectionText = document.getElementById("connection-text");

const clock = document.getElementById("clock");

const navButtons = document.querySelectorAll(".nav-button");
const pages = document.querySelectorAll(".page");
const clientSettingsButton = document.getElementById("client-settings-button");
const clientIdentityName = document.getElementById("client-identity-name");
const clientIdentityRoom = document.getElementById("client-identity-room");
const clientSetupModal = document.getElementById("client-setup-modal");
const clientSetupForm = document.getElementById("client-setup-form");
const clientNameInput = document.getElementById("client-name-input");
const clientRoomSelect = document.getElementById("client-room-select");
const newRoomInput = document.getElementById("new-room-input");
const addRoomButton = document.getElementById("add-room-button");
const clientSetupCancel = document.getElementById("client-setup-cancel");
const clientSetupStatus = document.getElementById("client-setup-status");

const CLIENT_ID_KEY = "nova_client_id";
const CLIENT_NAME_KEY = "nova_client_name";
const CLIENT_ROOM_KEY = "nova_room_id";

function createClientId() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }

    return `nova-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const novaClient = {
    id: localStorage.getItem(CLIENT_ID_KEY) || createClientId(),
    name: localStorage.getItem(CLIENT_NAME_KEY) || "",
    roomId: Number(localStorage.getItem(CLIENT_ROOM_KEY)) || null,
    roomName: "",
};

localStorage.setItem(CLIENT_ID_KEY, novaClient.id);

const allowedStatuses = [
    "idle",
    "listening",
    "thinking",
    "speaking",
    "working",
    "error",
];

const statusLabels = {
    idle: "Nova is ready",
    listening: "Nova is listening",
    thinking: "Nova is thinking",
    speaking: "Nova is speaking",
    working: "Nova is working",
    error: "Nova encountered an error",
};

let currentStatus = "idle";
let statusRequestInProgress = false;
let stateSocket = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let keepaliveTimer = null;


/*
|--------------------------------------------------------------------------
| Conversation messages
|--------------------------------------------------------------------------
*/

let historyLoaded = false;
let historySignature = "";
let historyRefreshTimer = null;

async function loadConversationHistory({ force = false } = {}) {
    if (!messagesContainer || (historyLoaded && !force)) {
        return;
    }

    try {
        const response = await fetch("/api/history?limit=80", {
            headers: { Accept: "application/json" },
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(`History request failed: ${response.status}`);
        }

        const data = await response.json();
        const messages = Array.isArray(data.messages) ? data.messages : [];
        const nextSignature = JSON.stringify(
            messages.map((message) => [
                message.id,
                message.role,
                message.content,
                message.source,
            ])
        );

        if (historyLoaded && nextSignature === historySignature) {
            return;
        }

        const wasNearBottom =
            messagesContainer.scrollHeight -
            messagesContainer.scrollTop -
            messagesContainer.clientHeight < 80;

        messagesContainer.innerHTML = "";

        if (!messages.length) {
            addMessage("Nova", "Hello. What can I help you with?", "nova", false);
        } else {
            messages.forEach((message) => {
                const isUser = message.role === "user";
                addMessage(
                    isUser ? "You" : "Nova",
                    message.content || "",
                    isUser ? "user" : (String(message.source || "").endsWith("error") ? "error" : "nova"),
                    false
                );
            });
        }

        historySignature = nextSignature;
        historyLoaded = true;

        if (wasNearBottom || !historySignature) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    } catch (error) {
        console.error("Unable to load conversation history:", error);
        if (!historyLoaded) {
            messagesContainer.innerHTML = "";
            addMessage("Nova", "Hello. What can I help you with?", "nova");
        }
    }
}

function startConversationSync() {
    if (historyRefreshTimer) return;
    historyRefreshTimer = window.setInterval(() => {
        if (!document.hidden) {
            loadConversationHistory({ force: true });
        }
    }, 1500);
}

function addMessage(sender, text, type = "nova", smoothScroll = true) {
    if (!messagesContainer) {
        return;
    }

    const message = document.createElement("div");
    message.classList.add("message");

    if (type === "user") {
        message.classList.add("user-message");
    } else if (type === "error") {
        message.classList.add("error-message");
    } else {
        message.classList.add("nova-message");
    }

    const name = document.createElement("span");
    name.className = "message-name";
    name.textContent = sender;

    const content = document.createElement("p");
    content.textContent = text;

    message.append(name, content);
    messagesContainer.appendChild(message);

    messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: smoothScroll ? "smooth" : "auto",
    });
}


/*
|--------------------------------------------------------------------------
| Connection indicator
|--------------------------------------------------------------------------
*/

function setConnected(isConnected) {
    if (!connectionDot || !connectionText) {
        return;
    }

    connectionDot.classList.toggle("online", isConnected);
    connectionDot.classList.toggle("offline", !isConnected);

    connectionText.textContent = isConnected
        ? "Nova online"
        : "Nova offline";
}


/*
|--------------------------------------------------------------------------
| Nova energy-ring state
|--------------------------------------------------------------------------
*/

function updateOrb(status) {
    if (!novaOrb || !orbLabel || !statusTitle) {
        return;
    }

    const safeStatus = allowedStatuses.includes(status)
        ? status
        : "idle";

    currentStatus = safeStatus;

    novaOrb.classList.remove(...allowedStatuses);
    novaOrb.classList.add(safeStatus);

    const label = statusLabels[safeStatus] ?? statusLabels.idle;

    orbLabel.textContent = label;

    statusTitle.textContent =
        safeStatus.charAt(0).toUpperCase() +
        safeStatus.slice(1);

    novaOrb.setAttribute(
        "aria-label",
        `Nova assistant status: ${safeStatus}`
    );
}


/*
|--------------------------------------------------------------------------
| Nova realtime state
|--------------------------------------------------------------------------
*/

function applyState(state) {
    if (!state || typeof state !== "object") {
        return;
    }

    updateOrb(
        typeof state.status === "string"
            ? state.status
            : "idle"
    );
}

async function fetchStatus() {
    if (statusRequestInProgress) {
        return;
    }

    statusRequestInProgress = true;

    try {
        const response = await fetch("/api/status", {
            method: "GET",
            headers: {
                Accept: "application/json",
            },
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(
                `Status request failed: ${response.status}`
            );
        }

        applyState(await response.json());
    } catch (error) {
        console.error("Unable to retrieve Nova status:", error);
    } finally {
        statusRequestInProgress = false;
    }
}

function scheduleReconnect() {
    if (reconnectTimer) {
        return;
    }

    const delay = Math.min(
        1000 * (2 ** reconnectAttempts),
        15000
    );

    reconnectAttempts += 1;

    reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectStateSocket();
    }, delay);
}

function stopKeepalive() {
    if (keepaliveTimer) {
        window.clearInterval(keepaliveTimer);
        keepaliveTimer = null;
    }
}

function connectStateSocket() {
    if (
        stateSocket &&
        [WebSocket.OPEN, WebSocket.CONNECTING].includes(
            stateSocket.readyState
        )
    ) {
        return;
    }

    const protocol = window.location.protocol === "https:"
        ? "wss:"
        : "ws:";

    stateSocket = new WebSocket(
        `${protocol}//${window.location.host}/ws/state`
    );

    stateSocket.addEventListener("open", () => {
        reconnectAttempts = 0;
        setConnected(true);

        stopKeepalive();
        registerSocketClient();

        keepaliveTimer = window.setInterval(() => {
            if (stateSocket?.readyState === WebSocket.OPEN) {
                stateSocket.send(JSON.stringify({ type: "ping" }));
            }
        }, 25000);
    });

    stateSocket.addEventListener("message", (event) => {
        try {
            const message = JSON.parse(event.data);

            if (message.type === "state") {
                applyState(message.data);
            } else if (message.type === "client_registered") {
                applyRegisteredClient(message.data);
            }
        } catch (error) {
            console.error("Invalid Nova WebSocket message:", error);
        }
    });

    stateSocket.addEventListener("close", async () => {
        stopKeepalive();
        setConnected(false);

        // Keep the REST endpoint as a one-shot fallback while reconnecting.
        await fetchStatus();
        scheduleReconnect();
    });

    stateSocket.addEventListener("error", () => {
        stateSocket?.close();
    });
}


/*
|--------------------------------------------------------------------------
| Send a command
|--------------------------------------------------------------------------
*/

async function sendCommand(command) {
    addMessage("You", command, "user");

    commandInput.disabled = true;
    sendButton.disabled = true;

    sendButton.textContent = "Working...";

    updateOrb("thinking");

    try {
        const response = await fetch("/api/command", {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },

            body: JSON.stringify({
                command,
                client_id: novaClient.id,
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();

            throw new Error(
                `Command failed (${response.status}): ${errorText}`
            );
        }

        const data = await response.json();

        const responseText =
            typeof data.response === "string" &&
            data.response.trim()
                ? data.response
                : "The command completed without a response.";

        addMessage("Nova", responseText, "nova");
    } catch (error) {
        console.error("Unable to process command:", error);

        addMessage(
            "Nova",
            "I couldn't process that request.",
            "error"
        );

        updateOrb("error");
    } finally {
        commandInput.disabled = false;
        sendButton.disabled = false;

        sendButton.textContent = "Send";

        commandInput.focus();

    }
}


/*
|--------------------------------------------------------------------------
| Command form
|--------------------------------------------------------------------------
*/

commandForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const command = commandInput.value.trim();

    if (!command) {
        commandInput.focus();
        return;
    }

    commandInput.value = "";

    await sendCommand(command);
});


/*
|--------------------------------------------------------------------------
| Clear conversation
|--------------------------------------------------------------------------
*/

clearButton?.addEventListener("click", async () => {
    clearButton.disabled = true;

    try {
        const response = await fetch("/api/history", { method: "DELETE" });

        if (!response.ok) {
            throw new Error(`Clear history failed: ${response.status}`);
        }

        historySignature = "";
        historyLoaded = false;
        messagesContainer.innerHTML = "";
        addMessage(
            "Nova",
            "Conversation cleared. What can I help you with?",
            "nova"
        );
    } catch (error) {
        console.error("Unable to clear conversation history:", error);
        addMessage("Nova", "I couldn't clear the saved conversation.", "error");
    } finally {
        clearButton.disabled = false;
        commandInput.focus();
    }
});


/*
|--------------------------------------------------------------------------
| Sidebar navigation
|--------------------------------------------------------------------------
*/

navButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const selectedPage = button.dataset.page;

        if (!selectedPage) {
            return;
        }

        navButtons.forEach((navButton) => {
            navButton.classList.remove("active");
            navButton.setAttribute("aria-current", "false");
        });

        button.classList.add("active");
        button.setAttribute("aria-current", "page");

        pages.forEach((page) => {
            page.classList.remove("active");
        });

        const selectedPageElement = document.getElementById(
            `${selectedPage}-page`
        );

        if (selectedPageElement) {
            selectedPageElement.classList.add("active");
        }
    });
});


/*
|--------------------------------------------------------------------------
| Clock
|--------------------------------------------------------------------------
*/

function updateClock() {
    if (!clock) {
        return;
    }

    const now = new Date();

    clock.textContent = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });

    clock.setAttribute(
        "title",
        now.toLocaleString()
    );
}


/*
|--------------------------------------------------------------------------
| Keyboard shortcuts
|--------------------------------------------------------------------------
*/

document.addEventListener("keydown", (event) => {
    const activeElement = document.activeElement;

    const isTyping =
        activeElement instanceof HTMLInputElement ||
        activeElement instanceof HTMLTextAreaElement;

    if (
        event.key === "/" &&
        !isTyping
    ) {
        event.preventDefault();
        commandInput.focus();
    }

    if (
        event.key === "Escape" &&
        activeElement === commandInput
    ) {
        commandInput.blur();
    }
});


/*
|--------------------------------------------------------------------------
| Browser visibility
|--------------------------------------------------------------------------
*/

document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
        connectStateSocket();
        loadConversationHistory({ force: true });
    }
});


/*
|--------------------------------------------------------------------------
| Initial setup
|--------------------------------------------------------------------------
*/

updateClock();
setInterval(updateClock, 1000);

updateOrb(currentStatus);
loadConversationHistory();
startConversationSync();
connectStateSocket();
initializeClientIdentity();

commandInput?.focus();


/*
|--------------------------------------------------------------------------
| Client and room identity
|--------------------------------------------------------------------------
*/

function updateClientIdentityDisplay() {
    if (clientIdentityName) {
        clientIdentityName.textContent = novaClient.name || "This display";
    }

    if (clientIdentityRoom) {
        clientIdentityRoom.textContent = novaClient.roomName || "Choose a room";
    }
}

function applyRegisteredClient(client) {
    if (!client || typeof client !== "object") return;

    novaClient.name = client.name || novaClient.name;
    novaClient.roomId = Number(client.room_id) || null;
    novaClient.roomName = client.room_name || "";

    localStorage.setItem(CLIENT_NAME_KEY, novaClient.name);
    if (novaClient.roomId) {
        localStorage.setItem(CLIENT_ROOM_KEY, String(novaClient.roomId));
    } else {
        localStorage.removeItem(CLIENT_ROOM_KEY);
    }

    updateClientIdentityDisplay();
}

function registerSocketClient() {
    if (stateSocket?.readyState !== WebSocket.OPEN || !novaClient.name) {
        return;
    }

    stateSocket.send(JSON.stringify({
        type: "register",
        client_id: novaClient.id,
        name: novaClient.name,
        room_id: novaClient.roomId,
    }));
}

async function loadRooms(selectedRoomId = novaClient.roomId) {
    const response = await fetch("/api/rooms", { cache: "no-store" });
    if (!response.ok) throw new Error(`Room request failed: ${response.status}`);

    const data = await response.json();
    const rooms = Array.isArray(data.rooms) ? data.rooms : [];

    if (!clientRoomSelect) return rooms;

    clientRoomSelect.innerHTML = "";
    rooms.forEach((room) => {
        const option = document.createElement("option");
        option.value = String(room.id);
        option.textContent = room.name;
        option.selected = Number(room.id) === Number(selectedRoomId);
        clientRoomSelect.appendChild(option);
    });

    if (!clientRoomSelect.value && rooms[0]) {
        clientRoomSelect.value = String(rooms[0].id);
    }

    return rooms;
}

async function loadExistingClient() {
    try {
        const response = await fetch(`/api/clients/${encodeURIComponent(novaClient.id)}`, {
            cache: "no-store",
        });
        if (!response.ok) throw new Error(`Client request failed: ${response.status}`);

        const data = await response.json();
        if (data.client) {
            applyRegisteredClient(data.client);
            return true;
        }
    } catch (error) {
        console.error("Unable to load Nova client identity:", error);
    }

    return false;
}

async function openClientSetup(force = false) {
    if (!clientSetupModal) return;

    try {
        await loadRooms();
        clientNameInput.value = novaClient.name || "Laptop Dashboard";
        if (novaClient.roomId) clientRoomSelect.value = String(novaClient.roomId);
        clientSetupStatus.textContent = "";
        clientSetupModal.hidden = false;
        clientSetupModal.dataset.required = force ? "true" : "false";
        clientSetupCancel.hidden = force;
        clientNameInput.focus();
    } catch (error) {
        console.error(error);
        clientSetupStatus.textContent = "Could not load rooms.";
    }
}

function closeClientSetup() {
    if (!clientSetupModal) return;
    if (clientSetupModal.dataset.required === "true") return;
    clientSetupModal.hidden = true;
}

clientSettingsButton?.addEventListener("click", () => openClientSetup(false));
clientSetupCancel?.addEventListener("click", closeClientSetup);

addRoomButton?.addEventListener("click", async () => {
    const name = newRoomInput.value.trim();
    if (!name) return;

    addRoomButton.disabled = true;
    clientSetupStatus.textContent = "";

    try {
        const response = await fetch("/api/rooms", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Could not create room.");
        }

        newRoomInput.value = "";
        await loadRooms(data.room.id);
    } catch (error) {
        clientSetupStatus.textContent = error.message || "Could not create room.";
    } finally {
        addRoomButton.disabled = false;
    }
});

clientSetupForm?.addEventListener("submit", async (event) => {
    event.preventDefault();

    const name = clientNameInput.value.trim();
    const roomId = Number(clientRoomSelect.value);
    if (!name || !roomId) return;

    clientSetupStatus.textContent = "Saving...";

    try {
        const response = await fetch(`/api/clients/${encodeURIComponent(novaClient.id)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                client_id: novaClient.id,
                name,
                room_id: roomId,
            }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Could not save display identity.");
        }

        applyRegisteredClient(data.client);
        clientSetupModal.dataset.required = "false";
        clientSetupModal.hidden = true;
        registerSocketClient();
    } catch (error) {
        clientSetupStatus.textContent = error.message || "Could not save display identity.";
    }
});

async function initializeClientIdentity() {
    updateClientIdentityDisplay();
    const exists = await loadExistingClient();

    if (!exists || !novaClient.name || !novaClient.roomId) {
        await openClientSetup(true);
    } else {
        registerSocketClient();
    }
}

/*
|--------------------------------------------------------------------------
| Music dashboard
|--------------------------------------------------------------------------
*/

const musicPage = document.getElementById("music-page");
const musicAlbumArt = document.getElementById("music-album-art");
const musicTrackName = document.getElementById("music-track-name");
const musicArtistName = document.getElementById("music-artist-name");
const musicAlbumName = document.getElementById("music-album-name");
const musicProgressTime = document.getElementById("music-progress-time");
const musicDurationTime = document.getElementById("music-duration-time");
const musicProgressFill = document.getElementById("music-progress-fill");
const musicPlayPause = document.getElementById("music-play-pause");
const musicPrevious = document.getElementById("music-previous");
const musicNext = document.getElementById("music-next");
const musicVolume = document.getElementById("music-volume");
const musicVolumeValue = document.getElementById("music-volume-value");
const musicDevice = document.getElementById("music-device");
const musicDeviceSelect = document.getElementById("music-device-select");
const musicDeviceRefresh = document.getElementById("music-device-refresh");
const musicSearchForm = document.getElementById("music-search-form");
const musicSearchInput = document.getElementById("music-search-input");
const musicSearchStatus = document.getElementById("music-search-status");
const musicSearchResults = document.getElementById("music-search-results");

let musicIsPlaying = false;
let musicRefreshTimer = null;
let volumeUpdateTimer = null;
let selectedSpotifyDeviceId = null;

function formatMusicTime(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor((milliseconds || 0) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function renderMusicState(playback) {
    if (!playback || typeof playback !== "object") return;

    const track = playback.track;
    musicIsPlaying = Boolean(playback.is_playing);

    if (musicPlayPause) {
        musicPlayPause.textContent = musicIsPlaying ? "Ⅱ" : "▶";
        musicPlayPause.setAttribute("aria-label", musicIsPlaying ? "Pause" : "Play");
    }

    if (track) {
        musicTrackName.textContent = track.name || "Unknown track";
        musicArtistName.textContent = track.artist || "Unknown artist";
        musicAlbumName.textContent = track.album || "";

        const artShell = musicAlbumArt?.parentElement;
        if (track.album_art && musicAlbumArt && artShell) {
            musicAlbumArt.src = track.album_art;
            artShell.classList.add("has-art");
        } else if (artShell) {
            artShell.classList.remove("has-art");
        }

        const duration = Number(track.duration_ms || 0);
        const progress = Number(playback.progress_ms || 0);
        const percent = duration > 0 ? Math.min(100, (progress / duration) * 100) : 0;

        musicProgressTime.textContent = formatMusicTime(progress);
        musicDurationTime.textContent = formatMusicTime(duration);
        musicProgressFill.style.width = `${percent}%`;
    } else {
        musicTrackName.textContent = "Nothing playing";
        musicArtistName.textContent = "Open Spotify or search below.";
        musicAlbumName.textContent = "";
        musicProgressTime.textContent = "0:00";
        musicDurationTime.textContent = "0:00";
        musicProgressFill.style.width = "0%";
        musicAlbumArt?.parentElement?.classList.remove("has-art");
    }

    const volume = Number.isFinite(playback.volume_percent)
        ? playback.volume_percent
        : 50;

    if (musicVolume && document.activeElement !== musicVolume) {
        musicVolume.value = String(volume);
    }
    if (musicVolumeValue) musicVolumeValue.textContent = `${volume}%`;
    selectedSpotifyDeviceId = playback.selected_device_id || selectedSpotifyDeviceId;
    if (musicDevice) {
        musicDevice.textContent = playback.device
            ? `Playing on ${playback.device}`
            : (selectedSpotifyDeviceId ? "Selected device is ready" : "No active Spotify device");
    }
    if (musicDeviceSelect && selectedSpotifyDeviceId) {
        musicDeviceSelect.value = selectedSpotifyDeviceId;
    }
}

async function refreshSpotifyDevices() {
    if (!musicDeviceSelect) return;

    try {
        const response = await fetch("/api/music/devices", { cache: "no-store" });
        if (!response.ok) throw new Error(`Device request failed: ${response.status}`);
        const data = await response.json();
        const devices = Array.isArray(data.devices) ? data.devices : [];

        musicDeviceSelect.innerHTML = "";
        if (!devices.length) {
            const option = new Option("Open Spotify on a playback device", "");
            musicDeviceSelect.add(option);
            musicDeviceSelect.disabled = true;
            selectedSpotifyDeviceId = null;
            return;
        }

        musicDeviceSelect.disabled = false;
        devices.forEach((device) => {
            const suffix = device.is_active ? " (active)" : "";
            const option = new Option(`${device.name} · ${device.type}${suffix}`, device.id);
            option.disabled = Boolean(device.is_restricted);
            musicDeviceSelect.add(option);
            if (device.is_selected) selectedSpotifyDeviceId = device.id;
        });

        if (selectedSpotifyDeviceId) musicDeviceSelect.value = selectedSpotifyDeviceId;
    } catch (error) {
        console.error("Unable to retrieve Spotify devices:", error);
    }
}

musicDeviceSelect?.addEventListener("change", async () => {
    const deviceId = musicDeviceSelect.value;
    if (!deviceId) return;
    musicDeviceSelect.disabled = true;
    try {
        await sendMusicAction("/api/music/device", { device_id: deviceId });
        selectedSpotifyDeviceId = deviceId;
        await refreshSpotifyDevices();
    } catch (error) {
        console.error(error);
        if (musicDevice) musicDevice.textContent = "Could not select that Spotify device";
    } finally {
        musicDeviceSelect.disabled = false;
    }
});

musicDeviceRefresh?.addEventListener("click", async () => {
    musicDeviceRefresh.disabled = true;
    try {
        await refreshSpotifyDevices();
        await refreshMusicState();
    } finally {
        musicDeviceRefresh.disabled = false;
    }
});

async function refreshMusicState() {
    if (!musicPage?.classList.contains("active")) return;

    try {
        const response = await fetch("/api/music/status", { cache: "no-store" });
        if (!response.ok) throw new Error(`Spotify status failed: ${response.status}`);
        renderMusicState(await response.json());
    } catch (error) {
        console.error("Unable to retrieve Spotify state:", error);
        if (musicDevice) musicDevice.textContent = "Spotify is unavailable";
    }
}

async function sendMusicAction(path, body = null) {
    const options = { method: "POST", headers: { Accept: "application/json" } };

    if (body) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
    }

    const response = await fetch(path, options);
    if (!response.ok) throw new Error(`Music command failed: ${response.status}`);

    await new Promise((resolve) => window.setTimeout(resolve, 350));
    await refreshMusicState();
}

musicPlayPause?.addEventListener("click", async () => {
    try {
        await sendMusicAction(musicIsPlaying ? "/api/music/pause" : "/api/music/resume");
    } catch (error) {
        console.error(error);
    }
});

musicPrevious?.addEventListener("click", () => sendMusicAction("/api/music/previous").catch(console.error));
musicNext?.addEventListener("click", () => sendMusicAction("/api/music/next").catch(console.error));

musicVolume?.addEventListener("input", () => {
    if (musicVolumeValue) musicVolumeValue.textContent = `${musicVolume.value}%`;

    window.clearTimeout(volumeUpdateTimer);
    volumeUpdateTimer = window.setTimeout(() => {
        sendMusicAction("/api/music/volume", {
            volume_percent: Number(musicVolume.value),
        }).catch(console.error);
    }, 250);
});

musicSearchForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = musicSearchInput.value.trim();
    if (!query) return;

    musicSearchStatus.textContent = "Searching Spotify...";
    musicSearchResults.innerHTML = "";

    try {
        const response = await fetch(`/api/music/search?query=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error(`Spotify search failed: ${response.status}`);

        const data = await response.json();
        const tracks = Array.isArray(data.tracks) ? data.tracks : [];
        musicSearchStatus.textContent = tracks.length
            ? `${tracks.length} result${tracks.length === 1 ? "" : "s"}`
            : "No tracks found.";

        tracks.forEach((track) => {
            const row = document.createElement("article");
            row.className = "music-result";

            const art = track.album_art
                ? Object.assign(document.createElement("img"), {
                    src: track.album_art,
                    alt: "",
                })
                : Object.assign(document.createElement("div"), {
                    className: "music-result-placeholder",
                    textContent: "♫",
                });

            const copy = document.createElement("div");
            copy.className = "music-result-copy";

            const title = document.createElement("strong");
            title.textContent = track.name;

            const subtitle = document.createElement("span");
            subtitle.textContent = `${track.artist} · ${track.album}`;

            const playButton = document.createElement("button");
            playButton.type = "button";
            playButton.textContent = "Play";
            playButton.addEventListener("click", async () => {
                playButton.disabled = true;
                try {
                    await sendMusicAction("/api/music/play", { uri: track.uri });
                } finally {
                    playButton.disabled = false;
                }
            });

            copy.append(title, subtitle);
            row.append(art, copy, playButton);
            musicSearchResults.appendChild(row);
        });
    } catch (error) {
        console.error(error);
        musicSearchStatus.textContent = "Spotify search failed.";
    }
});

function updateMusicRefreshLoop() {
    const isOpen = musicPage?.classList.contains("active");

    if (isOpen && !musicRefreshTimer) {
        refreshSpotifyDevices();
        refreshMusicState();
        musicRefreshTimer = window.setInterval(refreshMusicState, 3000);
    } else if (!isOpen && musicRefreshTimer) {
        window.clearInterval(musicRefreshTimer);
        musicRefreshTimer = null;
    }
}

navButtons.forEach((button) => {
    button.addEventListener("click", () => {
        window.setTimeout(updateMusicRefreshLoop, 0);
    });
});


/* Calendar dashboard */
const calendarPage = document.getElementById("calendar-page");
const calendarEvents = document.getElementById("calendar-events");
const calendarStatus = document.getElementById("calendar-status");
const calendarRefresh = document.getElementById("calendar-refresh");

function calendarDayLabel(dateString) {
    const date = new Date(`${dateString}T12:00:00`);
    const today = new Date();
    const tomorrow = new Date();
    tomorrow.setDate(today.getDate() + 1);
    const key = date.toDateString();
    if (key === today.toDateString()) return "Today";
    if (key === tomorrow.toDateString()) return "Tomorrow";
    return date.toLocaleDateString([], { weekday: "long" });
}

function renderCalendarEvents(events) {
    calendarEvents.innerHTML = "";
    if (!events.length) {
        calendarEvents.innerHTML = '<div class="empty-state">No events in the next seven days.</div>';
        return;
    }
    const groups = new Map();
    events.forEach((event) => {
        if (!groups.has(event.display_date)) groups.set(event.display_date, []);
        groups.get(event.display_date).push(event);
    });
    groups.forEach((items, date) => {
        const section = document.createElement("section");
        section.className = "calendar-day";
        const heading = document.createElement("div");
        heading.className = "calendar-day-heading";
        const strong = document.createElement("strong");
        strong.textContent = calendarDayLabel(date);
        const span = document.createElement("span");
        span.textContent = new Date(`${date}T12:00:00`).toLocaleDateString([], { month: "long", day: "numeric" });
        heading.append(strong, span);
        section.appendChild(heading);
        items.forEach((event) => {
            const row = document.createElement("article");
            row.className = "calendar-event";
            const time = document.createElement("div");
            time.className = "calendar-event-time";
            time.textContent = event.display_time;
            const copy = document.createElement("div");
            const title = document.createElement("h3");
            if (event.html_link) {
                const link = document.createElement("a");
                link.href = event.html_link;
                link.target = "_blank";
                link.rel = "noopener";
                link.textContent = event.title;
                title.appendChild(link);
            } else title.textContent = event.title;
            copy.appendChild(title);
            if (event.location) {
                const location = document.createElement("p");
                location.textContent = event.location;
                copy.appendChild(location);
            }
            if (event.description) {
                const description = document.createElement("p");
                description.textContent = event.description;
                copy.appendChild(description);
            }
            row.append(time, copy);
            section.appendChild(row);
        });
        calendarEvents.appendChild(section);
    });
}

async function refreshCalendar() {
    if (!calendarPage?.classList.contains("active")) return;
    calendarStatus.textContent = "Loading calendar...";
    try {
        const response = await fetch("/api/calendar/events?days=7", { cache: "no-store" });
        if (!response.ok) throw new Error(`Calendar failed: ${response.status}`);
        const data = await response.json();
        const events = Array.isArray(data.events) ? data.events : [];
        calendarStatus.textContent = `${events.length} upcoming event${events.length === 1 ? "" : "s"}`;
        renderCalendarEvents(events);
    } catch (error) {
        console.error(error);
        calendarStatus.textContent = "Calendar is unavailable. Check Google authentication and the server logs.";
        calendarEvents.innerHTML = "";
    }
}
calendarRefresh?.addEventListener("click", refreshCalendar);

/* Alarms dashboard */
const alarmsPage = document.getElementById("alarms-page");
const alarmsList = document.getElementById("alarms-list");
const alarmsStatus = document.getElementById("alarms-status");
const alarmsRefresh = document.getElementById("alarms-refresh");
const alarmForm = document.getElementById("alarm-form");
const alarmTime = document.getElementById("alarm-time");
const alarmLabel = document.getElementById("alarm-label");
const alarmFormStatus = document.getElementById("alarm-form-status");
const weekdayButtons = Array.from(document.querySelectorAll(".weekday-button"));
const weekdayPresetButtons = Array.from(document.querySelectorAll("[data-alarm-preset]"));
let alarmCountdownTimer = null;

const shortDayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function setSelectedAlarmDays(days) {
    const selected = new Set(days.map(Number));
    weekdayButtons.forEach((button) => {
        const active = selected.has(Number(button.dataset.day));
        button.classList.toggle("selected", active);
        button.setAttribute("aria-pressed", String(active));
    });
}

function selectedAlarmDays() {
    return weekdayButtons
        .filter((button) => button.classList.contains("selected"))
        .map((button) => Number(button.dataset.day));
}

weekdayButtons.forEach((button) => {
    button.addEventListener("click", () => {
        button.classList.toggle("selected");
        button.setAttribute("aria-pressed", String(button.classList.contains("selected")));
    });
});

weekdayPresetButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const preset = button.dataset.alarmPreset;
        if (preset === "weekdays") setSelectedAlarmDays([0, 1, 2, 3, 4]);
        if (preset === "weekends") setSelectedAlarmDays([5, 6]);
        if (preset === "daily") setSelectedAlarmDays([0, 1, 2, 3, 4, 5, 6]);
    });
});

function formatAlarmTime(time) {
    const [hour, minute] = String(time || "00:00").split(":").map(Number);
    const date = new Date();
    date.setHours(hour, minute, 0, 0);
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatAlarmDays(days) {
    const normalized = [...days].map(Number).sort((a, b) => a - b);
    if (normalized.join(",") === "0,1,2,3,4,5,6") return "Every day";
    if (normalized.join(",") === "0,1,2,3,4") return "Weekdays";
    if (normalized.join(",") === "5,6") return "Weekends";
    return normalized.map((day) => shortDayNames[day]).join(", ");
}

function formatCountdown(time) {
    if (!time) return "Disabled";
    const seconds = Math.max(0, Math.floor((new Date(time).getTime() - Date.now()) / 1000));
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (days) return `Next in ${days}d ${hours}h ${minutes}m`;
    if (hours) return `Next in ${hours}h ${minutes}m`;
    return `Next in ${minutes}m ${secs}s`;
}

function updateAlarmCountdowns() {
    document.querySelectorAll("[data-next-occurrence]").forEach((element) => {
        element.textContent = formatCountdown(element.dataset.nextOccurrence || null);
    });
}

async function setAlarmEnabled(alarm, enabled, toggle) {
    toggle.disabled = true;
    try {
        const response = await fetch(`/api/alarms/${encodeURIComponent(alarm.id)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({ enabled }),
        });
        if (!response.ok) throw new Error(`Update failed: ${response.status}`);
        await refreshAlarms();
    } catch (error) {
        console.error(error);
        alarmsStatus.textContent = "The alarm could not be updated.";
        toggle.checked = !enabled;
        toggle.disabled = false;
    }
}

function renderAlarms(alarms) {
    alarmsList.innerHTML = "";
    if (!alarms.length) {
        alarmsList.innerHTML = '<div class="empty-state">No weekly alarms have been created.</div>';
        return;
    }

    alarms.forEach((alarm) => {
        const row = document.createElement("article");
        row.className = "alarm-row weekly-alarm-row";
        row.classList.toggle("disabled", !alarm.enabled);

        const timeBlock = document.createElement("div");
        timeBlock.className = "alarm-time-block";
        const time = document.createElement("strong");
        time.textContent = formatAlarmTime(alarm.time);
        const days = document.createElement("span");
        days.textContent = formatAlarmDays(Array.isArray(alarm.days) ? alarm.days : []);
        timeBlock.append(time, days);

        const copy = document.createElement("div");
        copy.className = "alarm-copy";
        const title = document.createElement("h4");
        title.textContent = alarm.label || "Morning routine";
        const countdown = document.createElement("p");
        countdown.className = "alarm-countdown";
        countdown.dataset.nextOccurrence = alarm.next_occurrence || "";
        countdown.textContent = alarm.enabled ? formatCountdown(alarm.next_occurrence) : "Disabled";
        copy.append(title, countdown);

        const actions = document.createElement("div");
        actions.className = "alarm-actions";

        const switchLabel = document.createElement("label");
        switchLabel.className = "alarm-switch";
        switchLabel.setAttribute("aria-label", `${alarm.enabled ? "Disable" : "Enable"} ${alarm.label}`);
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.checked = Boolean(alarm.enabled);
        const slider = document.createElement("span");
        slider.className = "alarm-switch-slider";
        toggle.addEventListener("change", () => setAlarmEnabled(alarm, toggle.checked, toggle));
        switchLabel.append(toggle, slider);

        const remove = document.createElement("button");
        remove.className = "alarm-delete";
        remove.type = "button";
        remove.textContent = "Delete";
        remove.addEventListener("click", async () => {
            remove.disabled = true;
            try {
                const response = await fetch(`/api/alarms/${encodeURIComponent(alarm.id)}`, { method: "DELETE" });
                if (!response.ok) throw new Error(`Delete failed: ${response.status}`);
                await refreshAlarms();
            } catch (error) {
                console.error(error);
                alarmsStatus.textContent = "The alarm could not be deleted.";
                remove.disabled = false;
            }
        });

        actions.append(switchLabel, remove);
        row.append(timeBlock, copy, actions);
        alarmsList.appendChild(row);
    });
    updateAlarmCountdowns();
}

async function refreshAlarms() {
    if (!alarmsPage?.classList.contains("active")) return;
    alarmsStatus.textContent = "Loading alarms...";
    try {
        const response = await fetch("/api/alarms", { cache: "no-store" });
        if (!response.ok) throw new Error(`Alarms failed: ${response.status}`);
        const data = await response.json();
        const alarms = Array.isArray(data.alarms) ? data.alarms : [];
        const enabledCount = alarms.filter((alarm) => alarm.enabled).length;
        alarmsStatus.textContent = `${enabledCount} active · ${alarms.length} total`;
        renderAlarms(alarms);
    } catch (error) {
        console.error(error);
        alarmsStatus.textContent = "Alarms are unavailable.";
        alarmsList.innerHTML = "";
    }
}

alarmForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const days = selectedAlarmDays();
    if (!alarmTime?.value) {
        alarmFormStatus.textContent = "Choose an alarm time.";
        return;
    }
    if (!days.length) {
        alarmFormStatus.textContent = "Select at least one day.";
        return;
    }

    alarmFormStatus.textContent = "Creating alarm...";
    try {
        const response = await fetch("/api/alarms", {
            method: "POST",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: JSON.stringify({
                time: alarmTime.value,
                days,
                label: alarmLabel.value.trim() || "Morning routine",
                enabled: true,
            }),
        });
        if (!response.ok) throw new Error(await response.text());
        alarmFormStatus.textContent = "Weekly alarm created.";
        await refreshAlarms();
    } catch (error) {
        console.error(error);
        alarmFormStatus.textContent = "The alarm could not be created.";
    }
});
alarmsRefresh?.addEventListener("click", refreshAlarms);
setSelectedAlarmDays([0, 1, 2, 3, 4]);

function updateDataPages() {
    if (calendarPage?.classList.contains("active")) refreshCalendar();
    if (alarmsPage?.classList.contains("active")) {
        refreshAlarms();
        if (!alarmCountdownTimer) alarmCountdownTimer = window.setInterval(updateAlarmCountdowns, 1000);
    } else if (alarmCountdownTimer) {
        window.clearInterval(alarmCountdownTimer);
        alarmCountdownTimer = null;
    }
}
navButtons.forEach((button) => button.addEventListener("click", () => window.setTimeout(updateDataPages, 0)));
