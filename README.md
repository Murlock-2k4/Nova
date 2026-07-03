# Nova

> A modular local AI voice assistant built in Python.

Nova is a personal AI assistant designed to run locally on Windows. It combines offline speech recognition, local text-to-speech, a local language model, and external tools such as Spotify and Google Calendar to create a fast, private assistant that can control everyday tasks.

This project started as a learning project and is growing into a complete home assistant capable of running on a dedicated server with multiple voice nodes around the house.

---

## Features

- 🎤 Offline speech recognition (Vosk)
- 🗣️ Local text-to-speech (Piper)
- 🧠 Local AI using Ollama (Llama 3)
- 🎵 Spotify playback control
- 📅 Google Calendar integration
- 🌦️ Weather forecasts
- ⏰ Persistent alarms
- 🌅 Morning routine
- 💡 Smart-home ready architecture

---

## Demo

Current example:

```
You:
Hey Nova.

Nova:
Yes?

You:
Play Look At Me Now by Brennan Heart.

Nova:
Playing.

(Spotify opens and starts playback)
```

---

## Current Architecture

```
                 Voice
                   │
                   ▼
        Speech Recognition
              (Vosk)
                   │
                   ▼
               main.py
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     Weather   Calendar   Spotify
        │          │          │
        └──────────┼──────────┘
                   ▼
              Local AI
             (Ollama)
                   │
                   ▼
            Piper Text-to-Speech
```

---

## Technologies

- Python 3
- Ollama
- Llama 3
- Vosk
- Piper TTS
- Spotipy
- Google Calendar API
- Open-Meteo API

---

## Installation

Clone the repository:

```bash
git clone https://github.com/Murlock-2k4/Nova.git
cd Nova
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Install:

- Ollama
- Piper
- Vosk speech model

Create the following environment variables:

```
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

Add your own Google OAuth credentials:

```
credentials.json
```

Then run:

```bash
python main.py
```

---

## Roadmap

### Current

- [x] Wake word
- [x] Local AI
- [x] Spotify integration
- [x] Google Calendar
- [x] Weather
- [x] Persistent alarms
- [x] Morning routine

### In Progress

- [ ] Better conversation memory
- [ ] AI tool selection
- [ ] Smart home integration
- [ ] Home Assistant support
- [ ] Multi-room voice nodes

### Future

- [ ] Dedicated home server
- [ ] Raspberry Pi satellites
- [ ] Face recognition
- [ ] Camera support
- [ ] Local long-term memory

---

## Why I built Nova

I started Nova to learn more about Python, AI, APIs, and software architecture.

Instead of relying entirely on cloud services, my goal is to build a fast, privacy-focused assistant that runs primarily on local hardware while remaining modular and easy to extend.

The long-term vision is a distributed home assistant that can control music, lighting, calendars, routines, and other smart devices throughout the house.

---

## License

This project is currently released under the MIT License.
