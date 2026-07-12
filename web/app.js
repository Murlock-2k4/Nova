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

const navButtons = document.querySelectorAll(".nav-button");
const pages = document.querySelectorAll(".page");

const statusLabels = {
    idle: "Nova is ready",
    listening: "Nova is listening",
    thinking: "Nova is thinking",
    speaking: "Nova is speaking",
    working: "Nova is working",
    error: "Nova encountered an error",
};


function addMessage(sender, text, type = "nova") {
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

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}


function setConnected(isConnected) {
    connectionDot.classList.toggle("online", isConnected);
    connectionDot.classList.toggle("offline", !isConnected);

    connectionText.textContent = isConnected
        ? "Nova online"
        : "Nova offline";
}


function updateOrb(status) {
    const allowedStatuses = [
        "idle",
        "listening",
        "thinking",
        "speaking",
        "working",
        "error",
    ];

    const safeStatus = allowedStatuses.includes(status)
        ? status
        : "idle";

    novaOrb.className = `nova-orb ${safeStatus}`;

    const label = statusLabels[safeStatus] ?? "Nova is ready";

    orbLabel.textContent = label;

    statusTitle.textContent =
        safeStatus.charAt(0).toUpperCase() +
        safeStatus.slice(1);
}


async function fetchStatus() {
    try {
        const response = await fetch("/api/status");

        if (!response.ok) {
            throw new Error(`Status request failed: ${response.status}`);
        }

        const state = await response.json();

        setConnected(true);
        updateOrb(state.status);

    } catch (error) {
        setConnected(false);
        updateOrb("error");

        console.error(error);
    }
}


async function sendCommand(command) {
    addMessage("You", command, "user");

    commandInput.disabled = true;
    sendButton.disabled = true;

    updateOrb("thinking");

    try {
        const response = await fetch("/api/command", {
            method: "POST",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify({
                command: command,
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();

            throw new Error(
                `Command failed (${response.status}): ${errorText}`
            );
        }

        const data = await response.json();

        addMessage("Nova", data.response, "nova");

    } catch (error) {
        console.error(error);

        addMessage(
            "Nova",
            "I couldn't process that request.",
            "error"
        );

        updateOrb("error");

    } finally {
        commandInput.disabled = false;
        sendButton.disabled = false;

        commandInput.focus();

        await fetchStatus();
    }
}


commandForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const command = commandInput.value.trim();

    if (!command) {
        return;
    }

    commandInput.value = "";

    await sendCommand(command);
});


clearButton.addEventListener("click", () => {
    messagesContainer.innerHTML = "";

    addMessage(
        "Nova",
        "Conversation cleared. What can I help you with?",
        "nova"
    );
});


navButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const selectedPage = button.dataset.page;

        navButtons.forEach((navButton) => {
            navButton.classList.remove("active");
        });

        button.classList.add("active");

        pages.forEach((page) => {
            page.classList.remove("active");
        });

        const page = document.getElementById(`${selectedPage}-page`);

        if (page) {
            page.classList.add("active");
        }
    });
});


function updateClock() {
    const clock = document.getElementById("clock");

    const now = new Date();

    clock.textContent = now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });
}


updateClock();
setInterval(updateClock, 1000);

fetchStatus();
setInterval(fetchStatus, 800);

commandInput.focus();