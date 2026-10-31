# Animus Obscurus: what's new since your first copy

## 1.3.2
**New views**
- **Calendar:** a week of what's actually airing on AniList, day by day. Shows on your list come first and are highlighted. "Only my list" narrows it down, and long days fold into "Show more".
- **Stats:** episodes watched, estimated hours, your genres, ratings and status shelves. Pick a year for a recap built from your new watch log (Animus now remembers when you change episodes or statuses; older progress can't be dated).
- **Wide cards:** turn on **Wide cards** in the gear menu for roomier cards with the poster on the left and bigger buttons. Off by default.

**Smoother**
- The My list / Calendar / Discover / Stats switch and the status tabs now slide a pill between choices with a little jelly bounce.

**Episodes for long shows**
- **Season and episode buttons use the same themed menu as the rest of the app** instead of the browser's own list.
- **Every show's episode menu** has a "Go to episode" box: type a number and press Enter. Below it, episodes are grouped in 50s (E1 to E50, E51 to E100, ...), and the group you're on opens first. A short show is simply one group.

**Polish**
- The gear icon's tooltip and update dot no longer tilt when you hover it; only the cog turns.

## 1.3.1
**Updates install themselves**
- **Update now:** when a new version is out, the gear shows a red dot and the menu gets an **Update to vX.Y.Z** button at the top. One click downloads it, checks it, installs it and restarts Animus. Your list and settings are never touched, and a copy of the old files is kept in case anything goes wrong.
- **Check for updates / Check automatically** (new "Updates" group in the gear menu): look right now, or switch off the once-a-day check. With it off, Animus never contacts GitHub by itself.
- Updating needs this copy to be v1.3.1 or newer, so friends on 1.3.0 or older do one last manual update.

**Cleaner header**
- The title is now a big bold **ANIMUS** next to the eye logo, the same height as the logo. (The app is still Animus Obscurus everywhere else.)

## 1.3.0
**A tidier menu**
- **Settings is now a gear** that floats in the top right, under the mascot badge, the same size (or in its place if you have no mascot). It opens a menu in plain words, grouped into Look, Streaming, Friends and Your data, with a hint under each item.
- **What's new** sits at the bottom of that menu and shows this list inside the app.

- **Import from MyAnimeList** (under Your data): pick the export file you download from MAL (Profile, then Export; the .xml or .xml.gz file). It adds your shows with their status, episodes watched and score, and skips anything already on your list.

**Discover: find your next show**
- **My list / Discover switch** next to the title.
- **Season header** that follows the calendar ("Fall 2026"). Use the arrows to browse past seasons or see what's coming up.
- **Big cards** with the poster, score, format, episodes, studio, genres, a short synopsis and the countdown to the next episode.
- **+ Add to list** puts a show on your list in one click (it then says "On your list"). **Details** opens AniList.
- **Sort** by Most popular, Top rated, Airing soonest or New this week. Also a search box, a genre filter and **Hide shows on my list**.
- Season data is saved on your PC, so reopening a season is instant and works for a while offline.

## 1.2.0
**On every card**
- **Pin** (pushpin, bottom-left of the cover): pinned shows sort to the top of every tab.
- **Recommend** (thumbs-up next to the pin): marks a show to share with friends.
- **Rating:** flip the card and pick 1 to 10. It shows as a "9/10" chip on the front. New "Highest rated" sort.
- **Watching with:** flip the card and type who you're watching with. It shows on the front, and a new "With…" filter in the top bar lets you list shows by person.
- **Dropped:** a new status and tab, separate from On hold. Dropped covers are dimmed.

**Sharing**
- **Recommended tab:** every show you thumbs-upped, with an **Export my recommendations** button. It saves a small file you can send to a friend.
- **Friends tab:** use **Add a friend's file…** and their picks show up as cards with their rating and an **Add to my list** button. Each friend has a ✕ to remove their list.

**Themes**
- **Settings, then "Theme from a show…":** pick any cover from your list and the whole page takes on its colors, in both light and dark mode, with that show's art faded into the background. "Back to the default look" undoes it.

**Airing and sharing, made easier to find**
- The **Airing** tab sits at the far right of the tab row, apart from the others, in a contrasting color from your theme. It lists every show that has an episode still to air, whatever its status.
- **No duplicates from friends:** a show several friends recommended appears once ("2 friends"), listing who picked it and their ratings. Shows already on your list say "On your list", even if you titled them differently. Adding a friend's file again replaces their earlier list instead of piling up, and never changes your own list.
- **Settings** now has **Export my recommendations** and **Add a friend's recommendations…**, alongside the buttons on the Recommended and Friends tabs.

**Other**
- **New logo:** an anime-eye mark with a twinkling sparkle sits next to the name at the top, and it's also the browser tab icon. It takes its colors from your theme.
- **Settings, then "Your name…":** the name friends see on your recommendations.
- Backup and restore now include your friends' recommendations and your theme.
- The spreadsheet gained four columns (Rating, Pinned, Recommended, Watch With). Older lists open normally.

## 1.1.0
- **Airing tab:** shows that are still airing, soonest next episode first. Cards show "S1 E5 airs in 14h 36m".
- **✓ Watched button:** logs the next episode in one click, rolls into the next season, and marks a show Finished after its last episode (if it has stopped airing). The "change cover" action moved to the back of the card.
- **Add-title search:** type 2 or more letters in "Add an anime…" and pick from AniList results with posters. Picking one uses the exact right show, cover and seasons, and marks movies as movies.
- **Settings menu** (top bar) replaces the "Streaming site" button and adds:
  - **Back up my list:** downloads your list and settings as one zip.
  - **Restore from a backup…:** brings it back (your current list is kept as a .bak file first).
  - the version number.
- **Updates:** a small Update zip that replaces only the app files and never touches your list, covers or settings. New installs start with no streaming site chosen.

## 1.0.1 (small fixes and polish after the first zip)
- **Flip card:** the Remove button is gone from the front. A flip button turns the card over to show your notes (editable, they save as you type) with Remove at the bottom. A flip animation, and a flip-back button.
- **Themed dropdowns:** the status picker and the Sort, Year and Rating pickers in the top bar are now styled menus that match the page, with keyboard support, instead of the browser's plain popup.
- **New-episode highlight:** shows with a new episode out get a glowing purple outline. The little dot is gone. The "Finished" and "Not started" labels stay at the top of the card.
- **Faster, gentler startup:** year, genres and tags are saved on your computer and show instantly after a restart. Age ratings are fetched slowly in the background (at most about 40 requests a minute, with a 30-minute pause after any error) so the site that supplies them is not overloaded.
- **Fixes:** saving a brand-new empty list no longer fails. A few spots no longer break when the assets folder is missing.

## 1.0 (your first copy)
- Portable Windows app: unzip, double-click **Start Animus Obscurus.bat**, and the list opens in your browser.
- Any streaming site: **Streaming site** button sets where titles search, and the ▶ button asks once per season for a link to any episode, then opens the next episode for you.
- Covers, seasons and episode counts from AniList, with progress tracking per season and episode.
