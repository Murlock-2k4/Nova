import logging
import os
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import state
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE,
)

logger = logging.getLogger(__name__)

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
        "artist": ", ".join(
            artist.get("name", "Unknown artist") for artist in artists
        ),
        "album": album.get("name") or "Unknown album",
        "album_art": images[0].get("url") if images else None,
        "duration_ms": track.get("duration_ms") or 0,
    }


def get_playback_state() -> dict[str, Any]:
    try:
        playback = sp.current_playback()

        if not playback:
            state.set_music_playing(False)
            return {
                "available": False,
                "is_playing": False,
                "device": None,
                "volume_percent": 50,
                "progress_ms": 0,
                "track": None,
            }

        is_playing = bool(playback.get("is_playing"))
        state.set_music_playing(is_playing)

        device = playback.get("device") or {}
        item = playback.get("item")

        return {
            "available": True,
            "is_playing": is_playing,
            "device": device.get("name"),
            "volume_percent": device.get("volume_percent", 50),
            "progress_ms": playback.get("progress_ms") or 0,
            "track": _simplify_track(item) if item else None,
        }
    except Exception:
        logger.exception("Could not retrieve Spotify playback state")
        raise


def search_tracks(query: str, limit: int = 8) -> list[dict[str, Any]]:
    cleaned_query = query.strip()

    if not cleaned_query:
        return []

    results = sp.search(q=cleaned_query, type="track", limit=limit)
    tracks = results.get("tracks", {}).get("items", [])
    return [_simplify_track(track) for track in tracks]


def play_track_uri(track_uri: str) -> str:
    if not track_uri.startswith("spotify:track:"):
        raise ValueError("Invalid Spotify track URI")

    try:
        sp.start_playback(uris=[track_uri])
    except spotipy.SpotifyException as error:
        # A common case is that no active Spotify device exists yet.
        if error.http_status == 404:
            os.startfile(track_uri)
        else:
            raise

    state.set_music_playing(True)
    return "Playing track."


def play_song(song_request: str) -> str:
    song_request = song_request.strip()

    if not song_request:
        return "Tell me a song name."

    track_name, artist_name = split_song_and_artist(song_request)

    if artist_name:
        query = f'track:"{track_name}" artist:"{artist_name}"'
    else:
        query = f'track:"{track_name}"'

    tracks = search_tracks(query, limit=10)

    if not tracks:
        tracks = search_tracks(song_request, limit=10)

    if not tracks:
        return f"I couldn't find {song_request} on Spotify."

    best_track = tracks[0]
    play_track_uri(best_track["uri"])

    return f"Playing {best_track['name']} by {best_track['artist']}."


def pause_music() -> str:
    try:
        sp.pause_playback()
        state.set_music_playing(False)
        return "Paused music."
    except Exception:
        logger.exception("Spotify pause failed")
        return "I couldn't pause Spotify."


def resume_music() -> str:
    sp.start_playback()
    state.set_music_playing(True)
    return "Resumed music."


def next_track() -> str:
    sp.next_track()
    state.set_music_playing(True)
    return "Skipped to the next track."


def previous_track() -> str:
    sp.previous_track()
    state.set_music_playing(True)
    return "Returned to the previous track."


def set_volume(volume_percent: int) -> str:
    safe_volume = max(0, min(100, int(volume_percent)))
    sp.volume(safe_volume)
    return f"Spotify volume set to {safe_volume} percent."
