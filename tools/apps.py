import os
from pathlib import Path

START_MENU_PATHS = [
    Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs",
    Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
]

CUSTOM_APPS = {
    # Example:
    # "mygame": r"C:\Games\MyGame\game.exe",
}

def find_app(app_name: str):
    app_name = app_name.lower().strip()
    matches = []

    for start_path in START_MENU_PATHS:
        if not start_path.exists():
            continue

        for file in start_path.rglob("*.lnk"):
            if app_name in file.stem.lower():
                matches.append(file)

    return matches

def open_app(app_name: str) -> str:
    app_name = app_name.lower().strip()

    # Check custom apps first
    if app_name in CUSTOM_APPS:
        os.startfile(CUSTOM_APPS[app_name])
        return f"Opening {app_name}"

    matches = find_app(app_name)

    if not matches:
        return f"I couldn't find an app called {app_name}."

    best_match = matches[0]
    os.startfile(best_match)
    return f"Opening {best_match.stem}"