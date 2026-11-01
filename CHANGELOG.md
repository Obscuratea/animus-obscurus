# Animus Obscurus: what's new since your first copy

## 1.5.0
**New**
- **One card per show.** A show's seasons, movies, OVAs, specials and spin-offs on your list now share one card (a chip like "+2 · Movie, OVA" shows what's inside). Nothing on your list is merged or renamed: each entry keeps its own status and progress.
- **Open a card** by clicking it: it grows to fill the window, with tabs for **Seasons**, **Movies**, **OVAs** and **Specials**. Seasons are marked Watched, Watching or Not yet, with "Jump to this season". Each movie or OVA has its own status and ✓. Press **Esc** or ✕ to close it.
- **The page fills your window**, and the cards follow its width: more side by side on a big screen, stacked on a small one.
- **Card size** (gear → Look): **Wide** (the new default) or **Full width**, one long strip per show with its synopsis. The old small vertical cards are gone.
- **Flipping** works at every size: a full-width card's back uses both halves, and an opened card flips to the notes, rating and match of every entry in the show.
- **Watch dates from imports.** Importing from Anime-Planet or MyAnimeList now puts your real started and finished dates into **Stats**, so your past years fill in. Imports used to count every show as watched on the day you imported; **import the same file again** to fix that (nothing is added twice).
- On a card set to a later season, the title shows that season's name (for example "Initial D 2nd Stage" instead of "1st Stage").

**Fixes**
- Seasons no longer jump into a different series (MF Ghost showed Initial D's cover and seasons), and a movie or OVA between two seasons no longer cuts the season list short (Initial D now has all five stages; JoJo gains Stone Ocean).
- Names with "OVA", "Specials" or "Movie" in them are found (AniList's search returned nothing for "My Little Monster OVA"), and "Toradora! OVA" finds the OVA rather than a special. When AniList has no separate entry, the show is matched to the main series and listed in Check matches.
- Older wrong matches are corrected when the new matching is clearly better (Frieren matched to its chibi shorts).
- Movies imported from Anime-Planet show as movies.
- Check matches no longer lists shows whose name exactly matches an OVA or short on AniList.
- Covers that weren't found load without holding up the rest of the page while they are looked up again.
- The "Movie" label is centred, and the cards' background blur is lighter.

## 1.4.2
**New**
- **Upcoming tab.** Shows on your list that haven't premiered yet get their own tab (next to Not started), with the premiere date on the card.
- **Check matches.** Animus now tells you when a show may be linked to the wrong AniList entry (a special, an OVA, a short, or only a loose title fit) and lists them in one place, with **Looks right** or **Fix** for each. It's also under Import & export → Matching. Your list's names are never changed: fixing a match only changes the cover, seasons and details.
- The back of each card shows what the show is **Matched to** on AniList, and the cover button is now **Fix match**.
- Big lists (like a 1,000-show import) are linked in the background, many shows at a time, with a small progress note in the bottom-left corner.

**Fixes**
- Much better matching: the main series now wins over its specials, OVAs and shorts unless the name asks for one, season numbers ("2nd Season", "II") and years ("Dororo (2019)") are understood, and long titles find their show.
- Shows that weren't found are tried again the next day instead of staying blank forever, and renaming a show looks it up again.
- Covers no longer go missing on large imports (AniList now allows fewer requests per minute, and Animus waits its turn).
- The "already on your list" message when renaming stays up long enough to read, and suggests adding the year.
- No more error messages in the console window when a page is closed mid-load.

## 1.4.1
**New**
- **Import from Anime-Planet.** The new round **Import & export** button (under the gear) takes your Anime-Planet export file (.json) and adds the shows that aren't on your list yet, with their status, episodes watched and score. "Won't watch" shows are left out.
- **Import & export button.** Importing (MyAnimeList, Anime-Planet), backing up and restoring, and the friends' files moved out of the gear menu into it, so the gear is shorter.
- **Title language** (gear → Title language): show titles in English, Japanese in Latin letters (romaji), or Japanese script. Only the display changes; your saved names stay as they are, and searching finds a show under any of its titles.

## 1.4.0
**New**
- **Share your picks with a code.** Open **Friends**, tap **Share my picks** and send the code to a friend. They paste it under **Add friend**, and your 👍 picks stay up to date on their side with nothing to export again. Only your recommendations are shared, you can get a new code or stop sharing any time, and files still work too.
- **A Friends page** (the gold button, top right) now holds everything social: a "Your friends" card with a switch to show or hide each friend's picks, add and remove friends, and **Picks from friends**.
- **Compare** with a friend: what you both recommend, what they recommend that is already on your list, what they recommend that isn't, and what only you recommend.
- **Manga** has a place in the top bar, with a "Coming soon" page for now.
- Icons on the buttons that benefit from them (share, add, copy, remove, change cover, arrows and more), and in the settings panel.
- The title count at the top is gone: "All" at the bottom already shows it.

**Fixes**
- The episode picker no longer lists episodes that haven't aired. A season whose later part hasn't started used to count that part's planned episodes (a show with 5 out could offer 17).
- The Friends tab moved out of the bottom row into the new Friends page.

## 1.3.5
**New**
- **Special looks** (gear, "Special look"): Paper / Manga, Neon Tokyo and Retro 90s anime. You can also tint a look with the show you picked in "Theme from a show".
- **Continue watching**: a row of covers above the cards on the Started tab. Click one to open its next episode.
- **Synopsis** on the back of each card.
- **Keyboard shortcuts**: `/` search, `A` add, `1`-`4` switch view, `[` `]` change tab, `?` for help.
- If MyAnimeList's score isn't available, cards show AniList's score as "AL ★ 8.7" instead.

**Fixes**
- The theme background now stays on the season you picked after a reload.
- "What's new" only lists the last five updates.

## 1.3.4
**Fixes**
- Covers are no longer downloaded again and again (it was slow on slower connections).
- A show with no episode picked (E–) now always counts as Not started, whatever season is chosen.
- Movies show a plain MOVIE tag with no season or episode.
- Typing an episode number in the picker shows a "Go to" button right away, so you don't have to hunt through the groups of 50.
- The theme background now uses the cover of the season you picked, not always season 1.
- Later seasons of a show already on your list now show as "on your list" in Discover and can't be added twice.
- If a show ended up on the list twice (say "X" and "X Season 2"), a **Combine** button appears above the cards and merges them.
- Newly announced seasons show up within a day.

**New**
- **MyAnimeList score, rank and popularity** now show on each card, and you can sort by MAL score or MAL popularity.
- Coloured buttons now have a soft gradient.
- Changing the season on a show you're watching lands on E1 instead of dropping the show to Not started.

## 1.3.3
**Nicer to use**
- A back-to-top button pops up with a little bounce when you scroll down the page.

## 1.3.2
**New**
- **Calendar:** see what's airing this week, day by day. Shows on your list are highlighted and shown first.
- **Stats:** how many episodes and hours you've watched, your favorite genres, and a recap for any year.
- **Wide cards:** want bigger cards? Turn on "Wide cards" in the gear menu.

**Nicer to use**
- Picking an episode is easier: type a number to jump straight to it, or pick from groups of 50.
- The tabs now glide with a little bounce when you switch.
- Season and episode menus match the rest of the app.

## 1.3.1
**Updates**
- When a new version is out, the gear shows a red dot. Open it and tap "Update" and Animus updates itself. Your list is never touched.
- You can check for updates yourself or turn off the daily check in the gear menu.
- The title is now a big, bold ANIMUS next to the logo.

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
