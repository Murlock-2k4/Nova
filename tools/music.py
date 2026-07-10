import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import state

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE,
)

if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise RuntimeError(
        "Missing Spotify credentials. "
        "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET."
    )

SCOPE = "user-read-playback-state user-modify-playback-state"

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        open_browser=True,
    )
)


def split_song_and_artist(text: str):
    text = text.strip()

    if " by " in text.lower():
        parts = text.rsplit(" by ", 1)
        return parts[0].strip(), parts[1].strip()

    return text, None


def play_song(song_request: str) -> str:
    song_request = song_request.strip()

    if not song_request:
        return "Tell me a song name."

    track_name, artist_name = split_song_and_artist(song_request)

    if artist_name:
        query = f'track:"{track_name}" artist:"{artist_name}"'
    else:
        query = f'track:"{track_name}"'

    results = sp.search(q=query, type="track", limit=10)
    tracks = results.get("tracks", {}).get("items", [])

    if not tracks:
        fallback = sp.search(q=song_request, type="track", limit=10)
        tracks = fallback.get("tracks", {}).get("items", [])

    if not tracks:
        return f"I couldn't find {song_request} on Spotify."

    best_track = tracks[0]
    track_name = best_track["name"]
    artist_names = ", ".join(artist["name"] for artist in best_track["artists"])
    track_id = best_track["id"]

    state.music_is_playing = True
    os.startfile(f"spotify:track:{track_id}")

    return f"Opening {track_name} by {artist_names} in Spotify."


def pause_music() -> str:
    try:
        sp.pause_playback()
        state.music_is_playing = False
        return "Paused music."
    except Exception as error:
        print("Spotify pause error:", error)
        return "I couldn't pause Spotify."