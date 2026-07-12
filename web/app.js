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

function addMessage(sender, text, type = "nova") {
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
        behavior: "smooth",
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
        keepaliveTimer = window.setInterval(() => {
            if (stateSocket?.readyState === WebSocket.OPEN) {
                stateSocket.send("ping");
            }
        }, 25000);
    });

    stateSocket.addEventListener("message", (event) => {
        try {
            const message = JSON.parse(event.data);

            if (message.type === "state") {
                applyState(message.data);
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

clearButton?.addEventListener("click", () => {
    messagesContainer.innerHTML = "";

    addMessage(
        "Nova",
        "Conversation cleared. What can I help you with?",
        "nova"
    );

    commandInput.focus();
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
connectStateSocket();

commandInput?.focus();
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
const musicSearchForm = document.getElementById("music-search-form");
const musicSearchInput = document.getElementById("music-search-input");
const musicSearchStatus = document.getElementById("music-search-status");
const musicSearchResults = document.getElementById("music-search-results");

let musicIsPlaying = false;
let musicRefreshTimer = null;
let volumeUpdateTimer = null;

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
    if (musicDevice) {
        musicDevice.textContent = playback.device
            ? `Playing on ${playback.device}`
            : "No active Spotify device";
    }
}

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
