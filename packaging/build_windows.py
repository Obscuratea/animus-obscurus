#!/usr/bin/env python3
"""Build a portable Windows zip: the app plus python.org's embeddable Python, so nothing needs installing.

    python3 packaging/build_windows.py [--mascot]

Writes two zips into dist/:
  Animus-Obscurus-Windows-v<version>.zip  the full app with Python, for a first install
  Animus-Obscurus-Update-v<version>.zip   just the app files, to unzip over an existing install
The user's own list and covers (data/) are never included; a first run starts from template/.
Nyx (assets/) is left out unless --mascot is given. The version comes from server.py.
"""
import hashlib, io, os, re, sys, urllib.request, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "3.12.8"
VERSION = re.search(r'^VERSION = "([^"]+)"', open(os.path.join(ROOT, "server.py")).read(), re.M).group(1)
APP_FILES = ("server.py", "index.html", os.path.join("template", "Anime Watch List.xlsx"))
URL = f"https://www.python.org/ftp/python/{PY}/python-{PY}-embed-amd64.zip"
TOP = "Animus Obscurus"
BAT = '@echo off\r\ncd /d "%~dp0"\r\ntitle Animus Obscurus\r\n"python\\python.exe" server.py --open\r\nif errorlevel 1 pause\r\n'
README = """ANIMUS OBSCURUS - your anime list
=================================

1. Unzip this whole folder anywhere (not inside the zip itself).
2. Double-click "Start Animus Obscurus.bat". A black window opens and your browser
   shows the list. Keep the black window open while you use it; close it to stop.
   (If Windows SmartScreen warns about the .bat, choose More info > Run anyway.)

Use it
- Type a title in "Add an anime..." and press Add. Covers and season/episode counts
  come from AniList automatically (needs internet).
- Pick your season and episode with the dropdowns.
- Click "Streaming site" and follow the prompt once: it makes the show titles
  search on whichever site you like.
- Press the play button next to a show. The first time for each season it asks you to
  paste a link to any episode on your site; after that it opens the next episode
  for you, and the list keeps track of where you are.

Updating
- Later you may be sent an "Update" zip. Its UPDATE.txt explains it in 5 steps. Your list,
  covers and settings are in the "data" folder, which an update never touches.

Your list lives in the "data" folder (Anime Watch List.xlsx opens in Excel).
Copy that folder to back it up or move to a new PC.
"""


UPDATE_README = """ANIMUS OBSCURUS - update %s
==============================
Your list, covers and settings live in the "data" folder. This update does not contain
that folder, so they are not touched. See CHANGELOG.txt for what is new.

1. Close the black Animus window if it is open.
2. Open this zip (double-click it). Open the "Animus Obscurus" folder inside.
3. Press Ctrl+A to select everything in it, then drag it all into your own
   "Animus Obscurus" folder (the one with Start Animus Obscurus.bat in it).
4. When Windows asks, choose "Replace the files in the destination".
5. Double-click Start Animus Obscurus.bat as usual. In the page, open Settings at the top
   right: the bottom of that menu shows the version (%s).

From v1.3.1 on you won't need this zip: the gear menu shows "Update to ..." when a new
version is out, and one click installs it.

Tip: before updating, copy your "data" folder somewhere safe. It is your whole list.
The first start after an update fills in some info again from the internet, so give the
covers and "airing" times a minute.
"""


def add_app(z, mascot):
    for f in APP_FILES:
        z.write(os.path.join(ROOT, f), f"{TOP}/{f}".replace("\\", "/"))
    if mascot:
        adir = os.path.join(ROOT, "assets")
        for f in sorted(os.listdir(adir)):
            if os.path.isfile(os.path.join(adir, f)) and f.lower().endswith((".png", ".webp", ".gif", ".jpg", ".jpeg")):
                z.write(os.path.join(adir, f), f"{TOP}/assets/{f}")


def main():
    mascot = "--mascot" in sys.argv
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    update = os.path.join(ROOT, "dist", f"Animus-Obscurus-Update-v{VERSION}.zip")
    with zipfile.ZipFile(update, "w", zipfile.ZIP_DEFLATED) as z:
        add_app(z, False)
        z.write(os.path.join(ROOT, "CHANGELOG.md"), f"{TOP}/CHANGELOG.txt")
        z.writestr(f"{TOP}/UPDATE.txt", (UPDATE_README % (VERSION, VERSION)).replace("\n", "\r\n"))
    print("wrote", update, f"({os.path.getsize(update) // 1024} KB)")
    with open(update + ".sha256", "w") as f:   # the in-app updater checks the download against this
        f.write(hashlib.sha256(open(update, "rb").read()).hexdigest() + "\n")
    print("downloading", URL)
    emb = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(URL, timeout=60).read()))
    out = os.path.join(ROOT, "dist", f"Animus-Obscurus-Windows-v{VERSION}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in emb.infolist():
            z.writestr(f"{TOP}/python/{info.filename}", emb.read(info.filename))
        add_app(z, mascot)
        z.write(os.path.join(ROOT, "CHANGELOG.md"), f"{TOP}/CHANGELOG.txt")
        z.writestr(f"{TOP}/assets/", "")
        z.writestr(f"{TOP}/Start Animus Obscurus.bat", BAT)
        z.writestr(f"{TOP}/README.txt", README.replace("\n", "\r\n"))
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
