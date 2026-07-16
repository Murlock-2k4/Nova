import logging
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import state
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_PREFERRED_DEVICE,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE,
)
from database import get_setting, set_setting

logger = logging.getLogger(__name__)
DEVICE_SETTING_KEY = "spotify_device_id"

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise RuntimeError(
        "Missing Spotify credentials. "
        "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
    )

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        open_browser=True,
    )
)


def split_song_and_artist(text: str) -> tuple[str, str | None]:
    text = text.strip()
    lower_text = text.lower()
    if " by " in lower_text:
        split_at = lower_text.rfind(" by ")
        return text[:split_at].strip(), text[split_at + 4:].strip()
    return text, None


def _simplify_track(track: dict[str, Any]) -> dict[str, Any]:
    album = track.get("album") or {}
    images = album.get("images") or []
    artists = track.get("artists") or []
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "name": track.get("name") or "Unknown track",
        "artist": ", ".join(a.get("name", "Unknown artist") for a in artists),
        "album": album.get("name") or "Unknown album",
        "album_art": images[0].get("url") if images else None,
        "duration_ms": track.get("duration_ms") or 0,
    }


def get_devices() -> list[dict[str, Any]]:
    devices = sp.devices().get("devices", [])
    selected_id = get_setting(DEVICE_SETTING_KEY)
    return [
        {
            "id": device.get("id"),
            "name": device.get("name") or "Unnamed device",
            "type": device.get("type") or "Unknown",
            "is_active": bool(device.get("is_active")),
            "is_restricted": bool(device.get("is_restricted")),
            "volume_percent": device.get("volume_percent"),
            "is_selected": device.get("id") == selected_id,
        }
        for device in devices
        if device.get("id")
    ]


def select_device(device_id: str) -> str:
    device = next((d for d in get_devices() if d["id"] == device_id), None)
    if not device:
        raise ValueError("That Spotify device is not currently available")
    if device["is_restricted"]:
        raise ValueError("That Spotify device cannot be controlled remotely")
    set_setting(DEVICE_SETTING_KEY, device_id)
    return f"Selected {device['name']} for Spotify playback."


def _resolve_device() -> dict[str, Any] | None:
    devices = get_devices()
    if not devices:
        return None

    saved_id = get_setting(DEVICE_SETTING_KEY)
    if saved_id:
        saved = next((d for d in devices if d["id"] == saved_id), None)
        if saved and not saved["is_restricted"]:
            return saved

    if SPOTIFY_PREFERRED_DEVICE:
        wanted = SPOTIFY_PREFERRED_DEVICE.casefold()
        preferred = next(
            (d for d in devices if d["name"].casefold() == wanted and not d["is_restricted"]),
            None,
        )
        if preferred:
            set_setting(DEVICE_SETTING_KEY, preferred["id"])
            return preferred

    active = next((d for d in devices if d["is_active"] and not d["is_restricted"]), None)
    if active:
        set_setting(DEVICE_SETTING_KEY, active["id"])
        return active

    available = next((d for d in devices if not d["is_restricted"]), None)
    if available:
        set_setting(DEVICE_SETTING_KEY, available["id"])
    return available


def _require_device() -> dict[str, Any]:
    device = _resolve_device()
    if not device:
        raise RuntimeError(
            "No Spotify Connect device is available. Open Spotify on the "
            "computer, phone, speaker, or TV you want Nova to control."
        )
    return device


def get_playback_state() -> dict[str, Any]:
    playback = sp.current_playback()
    selected = _resolve_device()
    if not playback:
        state.set_music_playing(False)
        return {
            "available": False, "is_playing": False,
            "device": selected["name"] if selected else None,
            "selected_device_id": selected["id"] if selected else None,
            "volume_percent": selected.get("volume_percent", 50) if selected else 50,
            "progress_ms": 0, "track": None,
        }

    is_playing = bool(playback.get("is_playing"))
    state.set_music_playing(is_playing)
    device = playback.get("device") or {}
    item = playback.get("item")
    return {
        "available": True, "is_playing": is_playing,
        "device": device.get("name"),
        "selected_device_id": selected["id"] if selected else None,
        "volume_percent": device.get("volume_percent", 50),
        "progress_ms": playback.get("progress_ms") or 0,
        "track": _simplify_track(item) if item else None,
    }


def search_tracks(query: str, limit: int = 8) -> list[dict[str, Any]]:
    cleaned_query = query.strip()
    if not cleaned_query:
        return []
    results = sp.search(q=cleaned_query, type="track", limit=limit)
    return [_simplify_track(t) for t in results.get("tracks", {}).get("items", [])]


def play_track_uri(track_uri: str) -> str:
    if not track_uri.startswith("spotify:track:"):
        raise ValueError("Invalid Spotify track URI")
    device = _require_device()
    sp.start_playback(device_id=device["id"], uris=[track_uri])
    state.set_music_playing(True)
    return f"Playing on {device['name']}."


def play_song(song_request: str) -> str:
    song_request = song_request.strip()
    if not song_request:
        return "Tell me a song name."
    track_name, artist_name = split_song_and_artist(song_request)
    query = f'track:"{track_name}" artist:"{artist_name}"' if artist_name else f'track:"{track_name}"'
    tracks = search_tracks(query, 10) or search_tracks(song_request, 10)
    if not tracks:
        return f"I couldn't find {song_request} on Spotify."
    best = tracks[0]
    try:
        device_message = play_track_uri(best["uri"])
    except RuntimeError as error:
        return str(error)
    return f"Playing {best['name']} by {best['artist']}. {device_message}"


def pause_music() -> str:
    try:
        device = _require_device()
        sp.pause_playback(device_id=device["id"])
        state.set_music_playing(False)
        return f"Paused Spotify on {device['name']}."
    except Exception as error:
        logger.exception("Spotify pause failed")
        return str(error)


def resume_music() -> str:
    device = _require_device()
    sp.transfer_playback(device_id=device["id"], force_play=True)
    state.set_music_playing(True)
    return f"Resumed Spotify on {device['name']}."


def next_track() -> str:
    device = _require_device()
    sp.next_track(device_id=device["id"])
    state.set_music_playing(True)
    return f"Skipped to the next track on {device['name']}."


def previous_track() -> str:
    device = _require_device()
    sp.previous_track(device_id=device["id"])
    state.set_music_playing(True)
    return f"Returned to the previous track on {device['name']}."


def set_volume(volume_percent: int) -> str:
    device = _require_device()
    safe_volume = max(0, min(100, int(volume_percent)))
    sp.volume(safe_volume, device_id=device["id"])
    return f"Spotify volume on {device['name']} set to {safe_volume} percent."
