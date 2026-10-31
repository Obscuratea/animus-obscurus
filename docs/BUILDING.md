# Building and releasing

Animus Obscurus needs only Python 3.9+ (standard library). Building the Windows packages and publishing a release
are done with the scripts in `packaging/`.

## Build the packages

```
python3 packaging/build_windows.py
```

Writes to `dist/` (not tracked by git):

- `Animus-Obscurus-Windows-vX.Y.Z.zip`: the full app with an embeddable Python 3.12 (downloaded once), a blank list template and a start script.
- `Animus-Obscurus-Update-vX.Y.Z.zip`: only the app files, for the in-app updater.
- `Animus-Obscurus-Update-vX.Y.Z.zip.sha256`: the checksum the updater verifies before installing.

The version comes from `VERSION` in `server.py`. User data (`data/`) and mascot art (`assets/`) are never included
(pass `--mascot` to put the images in `assets/` into the full zip).

## Release checklist

1. Make the changes in a git working copy (the updater refuses to run in a folder with `.git`).
2. Bump `VERSION` in `server.py`.
3. Add a `## X.Y.Z` section to `CHANGELOG.md`. It is shown in the app under the gear menu, "What's new", and used as the release notes.
4. For a major (x.0.0) or minor (x.y.0) release, also make a new `docs/latest-release.png` and update the
   "Latest release features" section of `README.md`. `release.py` refuses to publish an x.y.0 release unless the README mentions it.
   Patch releases skip this.
5. Run `python3 packaging/build_windows.py`.
6. Commit and push, then publish:

```
python3 packaging/release.py          # asks y/N first
python3 packaging/release.py --yes    # no prompt
```

`release.py` needs the [GitHub CLI](https://cli.github.com/) (`gh`) logged in. It creates the `vX.Y.Z` release and uploads the
three files above. Installed copies find it through the GitHub Releases API, so the update zip and its `.sha256`
must both be attached.

## Updater notes

- The updater checks `UPDATE_REPO` in `server.py` (fork it? change that). Set `ANIMUS_UPDATE_API` to test against a local fake release.
- It replaces only `server.py`, `index.html`, `template/Anime Watch List.xlsx` and `CHANGELOG.txt`, keeps a rollback copy in `.update-backup/`, and never touches `data/`.
