# Animus Obscurus

A personal anime tracker that runs on your own computer. No account, no cloud: your list lives in a spreadsheet next to the app.

- **Track episodes on any streaming site.** Paste one episode link per season and the ▶ button opens the next episode.
- **Airing tab, covers, ratings and genres** from AniList (cached on disk, so MyAnimeList's Jikan API is barely touched).
- **Discover** what's airing this season (or any past or upcoming one) and add it to your list in one click.
- **Share recommendations with friends** as a small file, no server needed.
- **Import your MyAnimeList** export file.
- **Themes from any show's cover**, backups, and **one-click updates** from GitHub Releases.

## Latest release features

![Animus Obscurus v1.3.1: one-click updates, Discover, MyAnimeList import](docs/latest-release.png)

**[Get v1.3.1](../../releases/latest)**. The full list of changes is in [CHANGELOG.md](CHANGELOG.md), and in the app under the gear menu → What's new.

## Run it

Python 3.9+ and nothing else (standard library only):

```
python3 server.py 8765
```

Then open <http://127.0.0.1:8765>. On Linux, `./run.sh` does both. On Windows, download the full zip from the [Releases](../../releases) page (it bundles Python), unzip it, and double-click **Start Animus Obscurus.bat**.

Your data (list, covers, settings) is stored in the `data/` folder and is never part of an update. Optional mascot art goes in `assets/` (any image there becomes a mascot).

## Updating

When a new release is out, the gear icon gets a red dot and its menu shows **Update to vX.Y.Z**. One click downloads it, verifies its SHA-256 checksum, replaces only the app files and restarts. You can turn the daily check off in the same menu.

## Building a release

```
python3 packaging/build_windows.py   # full Windows zip + update zip + checksum into dist/
python3 packaging/release.py         # publishes them as a GitHub Release (needs `gh`)
```
