#!/usr/bin/env python3
"""Local anime list: serves index.html and keeps the Excel sheet in sync. Stdlib only."""
import difflib, functools, hashlib, io, json, mimetypes, os, re, secrets, shutil, sys, tempfile, threading, time, unicodedata, urllib.error, urllib.request, webbrowser, zipfile
from urllib.parse import parse_qs, unquote, urlparse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

VERSION = "1.4.2"
ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
MASCOT_EXTS = (".png", ".webp", ".gif", ".jpg", ".jpeg")
XLSX = os.path.join(ROOT, "data", "Anime Watch List.xlsx")
SHEET = "xl/worksheets/sheet1.xml"
SST = "xl/sharedStrings.xml"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TEMPLATE = os.path.join(ROOT, "template", "Anime Watch List.xlsx")   # blank list for a first run
SETTINGS = os.path.join(ROOT, "data", "settings.json")
DEFAULT_SEARCH = "https://miruro.cx/search?query={q}"   # used until settings.json exists
FIRST_ROW = 3          # rows 1-2 are the link + header
STYLES = {"A": 6, "B": 6, "C": 7, "D": 8, "E": 8, "F": 8, "G": 8, "H": 8, "I": 8, "J": 8}
HEADERS = {"B": "Season / Episode", "C": "Status", "D": "Notes", "E": "Cover URL", "F": "Watch Links",
           "G": "Rating", "H": "Pinned", "I": "Recommended", "J": "Watch With"}
# Status column values as written to the sheet, keyed by the page's status ids.
STATUS_LABELS = {"not started": "Not started", "started": "Started",
                 "on hold": "On hold", "finished": "Finished", "dropped": "Dropped"}
FROM_SHEET = {v.lower(): k for k, v in STATUS_LABELS.items()}
FROM_SHEET.update({"comepleted": "finished", "completed": "finished"})  # original sheet's spelling


def read_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"search": DEFAULT_SEARCH}


def ensure_list():
    """A fresh install has no list yet: start from the blank one."""
    if not os.path.exists(XLSX) and os.path.exists(TEMPLATE):
        os.makedirs(os.path.dirname(XLSX), exist_ok=True)
        shutil.copy2(TEMPLATE, XLSX)
        if not os.path.exists(SETTINGS):
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({"search": ""}, f, indent=1)


def clean_rating(v):
    """A 1-10 rating as text, or "" for none."""
    try:
        n = int(float(str(v).strip()))
    except ValueError:
        return ""
    return str(n) if 1 <= n <= 10 else ""


def read_items(path=None):
    with zipfile.ZipFile(path or XLSX) as z:
        shared = [
            "".join(t.text or "" for t in si.iter(NS + "t"))
            for si in ET.fromstring(z.read(SST))
        ]
        sheet = ET.fromstring(z.read(SHEET))
    items = []
    for row in sheet.iter(NS + "row"):
        n = int(row.get("r"))
        if n < FIRST_ROW:
            continue
        vals = {}
        for c in row.findall(NS + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            if col not in STYLES:
                continue
            if c.get("t") == "inlineStr":
                vals[col] = "".join(t.text or "" for t in c.iter(NS + "t"))
                continue
            v = c.find(NS + "v")
            if v is None or v.text is None:
                continue
            vals[col] = shared[int(v.text)] if c.get("t") == "s" else v.text
        name = vals.get("A", "").strip()
        if not name:
            continue
        prog = vals.get("B", "").strip()
        if re.fullmatch(r"0(\.0+)?", prog):
            prog = ""
        # Legacy "x" (or blank) meant "not finished": started if there is progress.
        status = FROM_SHEET.get(vals.get("C", "").strip().lower(),
                                "started" if prog else "not started")
        items.append({
            "name": name,
            "progress": prog,
            "status": status,
            "notes": vals.get("D", "").strip(),
            "cover": vals.get("E", "").strip(),
            "links": vals.get("F", "").strip(),
            "rating": clean_rating(vals.get("G", "")),
            "pinned": vals.get("H", "").strip().lower() == "yes",
            "rec": vals.get("I", "").strip().lower() == "yes",
            "with": vals.get("J", "").strip(),
        })
    return items


def cell(ref, col, text):
    s = STYLES[col]
    if text == "":
        return f'<c r="{ref}" s="{s}"/>'
    return (f'<c r="{ref}" s="{s}" t="inlineStr"><is>'
            f'<t xml:space="preserve">{escape(text)}</t></is></c>')


def write_items(items):
    rows = []
    for i, it in enumerate(items):
        r = FIRST_ROW + i
        status = STATUS_LABELS[it["status"]]
        b = (f'<c r="B{r}" s="6"><v>0</v></c>' if not it["progress"]
             else cell(f"B{r}", "B", it["progress"]))
        rows.append(
            f'<row r="{r}">{cell(f"A{r}", "A", it["name"])}{b}'
            f'{cell(f"C{r}", "C", status)}{cell(f"D{r}", "D", it["notes"])}'
            f'{cell(f"E{r}", "E", it["cover"])}{cell(f"F{r}", "F", it["links"])}'
            f'{cell(f"G{r}", "G", it["rating"])}{cell(f"H{r}", "H", "yes" if it["pinned"] else "")}'
            f'{cell(f"I{r}", "I", "yes" if it["rec"] else "")}{cell(f"J{r}", "J", it["with"])}</row>'
        )
    last = FIRST_ROW + max(len(items), 1) - 1
    with zipfile.ZipFile(XLSX) as z:
        xml = z.read(SHEET).decode("utf-8")
        head = re.search(r"<sheetData>(.*?)(?=<row r=\"3\"|</sheetData>)", xml, re.S).group(1)
        for col, label in HEADERS.items():
            head = re.sub(rf'<c r="{col}2"[^>]*?(?:/>|>.*?</c>)',
                          f'<c r="{col}2" s="4" t="inlineStr"><is><t>{label}</t></is></c>',
                          head, count=1, flags=re.S)
        xml = re.sub(r"<sheetData>.*</sheetData>",
                     lambda m: "<sheetData>" + head + "".join(rows) + "</sheetData>",
                     xml, flags=re.S)
        xml = re.sub(r'(<dataValidation [^>]*sqref=")C3:C\d+', rf"\g<1>C3:C{max(last, 1000)}", xml)
        xml = re.sub(r"(<formula1>).*?(</formula1>)",
                     "\\g<1>&quot;" + ",".join(STATUS_LABELS.values()) + "&quot;\\g<2>", xml)
        fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=os.path.dirname(XLSX))
        os.close(fd)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
            for info in z.infolist():
                data = xml.encode("utf-8") if info.filename == SHEET else z.read(info.filename)
                out.writestr(info, data)
    shutil.copy2(XLSX, XLSX + ".bak")
    os.replace(tmp, XLSX)


COVERS = os.path.join(ROOT, "data", "covers")
COVER_DB = os.path.join(COVERS, "covers.json")
cover_lock = threading.Lock()
seasons_lock = threading.Lock()
QUERY = """query($s:String){Media(search:$s,type:ANIME){id format seasonYear startDate{year} title{romaji english} coverImage{large}}}"""
ID_QUERY = """query($id:Int){Media(id:$id,type:ANIME){id format seasonYear startDate{year} title{romaji english} coverImage{large}}}"""
SEARCH_QUERY = """query($s:String){Page(perPage:8){media(search:$s,type:ANIME,sort:SEARCH_MATCH){
  id format seasonYear title{romaji english} coverImage{medium}}}}"""
SEASON_FIELDS = ("id format status episodes title{romaji english native} coverImage{large} nextAiringEpisode{episode airingAt} "
                 "relations{edges{relationType node{id format title{romaji english}}}}")
SEASON_QUERY = "query($id:Int){Media(id:$id){" + SEASON_FIELDS + "}}"
SEASONS_DB = os.path.join(ROOT, "data", "seasons.json")
SEASONS_V = 4             # bump when the shape or meaning of cached seasons changes
AIRING_TTL = 3 * 3600     # airing shows gain episodes weekly
SEASONS_TTL = 24 * 3600   # a day: a newly announced sequel should show up soon
SEASON_FORMATS = ("TV", "TV_SHORT", "ONA")   # entries that count as a season
BRIDGE_FORMATS = ("MOVIE", "OVA")             # walked through to reach the next season, not listed
rate_lock = threading.Lock()
next_slot = [0.0]


ANILIST_GAP = 2.1   # AniList allows 30 calls a minute (X-RateLimit-Limit); one every 2 s stays under it


def gql(query, variables, key="Media"):
    """One AniList call, spaced out to stay under their rate limit (retrying on 429)."""
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://graphql.anilist.co", body,
                                 {"Content-Type": "application/json", "User-Agent": "anime-list"})
    for attempt in range(6):
        with rate_lock:
            now = time.time()
            wait = next_slot[0] - now
            next_slot[0] = max(now, next_slot[0]) + ANILIST_GAP
        if wait > 0:
            time.sleep(wait)
        try:
            data = json.load(urllib.request.urlopen(req, timeout=20))["data"]
            return data if key is None else data[key]
        except urllib.error.HTTPError as e:
            if e.code == 404 and key is None:   # a batch where some ids are gone: keep the rest
                try:
                    return json.load(e).get("data") or {}
                except ValueError:
                    raise e
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 5))


def save_covers(db):
    os.makedirs(COVERS, exist_ok=True)   # a fresh install has no covers folder yet
    with open(COVER_DB, "w") as f:
        json.dump(db, f, indent=1)


def load_covers():
    try:
        with open(COVER_DB) as f:
            db = json.load(f)
    except FileNotFoundError:
        return {}
    for ent in db.values():   # copies before 1.4.2 saved only the file, which is named after the AniList id
        stem = (ent.get("file") or "").split(".")[0]
        if "id" not in ent and stem.isdigit():
            ent["id"] = int(stem)
    return db


SEASON_WORDS = re.compile(r"\s*[:\-–]?\s*\b(season\s*\d+|\d+(?:st|nd|rd|th)\s+season|(?:second|third|fourth|fifth|final)\s+season|part\s*\d+|cour\s*\d+)\b.*$", re.I)


def search_terms(name):
    """The title as written, then looser versions (sheet names carry extras like ': Netflix')."""
    loose = re.sub(r"\s*[:\-–]\s*(netflix|season\s*\d+|s\d+).*$", "", name, flags=re.I)
    bare = SEASON_WORDS.sub("", name).strip()   # "Haikyu!! Second Season" -> "Haikyu!!" (the season is picked by number after)
    # AniList finds nothing for "My Little Monster OVA"; the format words still steer the pick (score_candidate sees the full name)
    plain = " ".join(re.sub(r"[(\[]\s*[)\]]", " ", FORMAT_WORDS.sub(" ", name)).split()).strip(" :-–")
    unnumbered = re.sub(r"\s+(\d{1,2}|ii|iii|iv)$", "", bare, flags=re.I)   # "Kamisama Kiss 2" is "Kamisama Kiss◎" on AniList
    return list(dict.fromkeys(t for t in [name, loose, plain, bare, unnumbered, name.split(":")[0].strip()] if t))


FORMAT_WORDS = re.compile(r"\b(?:the\s+)?(?:ova|oav|oad|ona|specials?|recap|movies?|film|tv\s+series|tv)\b", re.I)


# ---- Matching a list name to the right AniList entry. The name on the list is never changed; only the match behind it.
CAND_FIELDS = "id format seasonYear startDate{year} title{romaji english native} synonyms coverImage{large}"
CAND_QUERY = "query($s:String){Page(perPage:8){media(search:$s,type:ANIME,sort:SEARCH_MATCH){" + CAND_FIELDS + "}}}"
MATCH_V = 4   # bump when matching improves, so automatic matches are re-checked once
MINOR_FORMATS = ("SPECIAL", "OVA", "MUSIC", "TV_SHORT")
MINOR_WORDS = re.compile(r"\b(ova|oad|specials?|recap|shorts?|chibi|pilot|mini|music|pv|omake|picture drama)\b", re.I)
MOVIE_WORDS = re.compile(r"\b(movie|film|gekijouban)\b", re.I)
YEAR_RE = re.compile(r"\s*[(\[]((?:19|20)\d\d)[)\]]")
FORMAT_PRIOR = {"TV": .1, "MOVIE": .06, "ONA": .06, "TV_SHORT": -.05, "OVA": -.1, "SPECIAL": -.15, "MUSIC": -.2}
ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "second": "2", "third": "3", "fourth": "4", "fifth": "5"}
NEG_RETRY = 24 * 3600     # a title AniList didn't know is asked about again after a day


def split_year(name):
    """'Dororo (2019)' -> ('Dororo', 2019): sites add the year to tell remakes apart; AniList can't search for it."""
    m = YEAR_RE.search(name)
    return (YEAR_RE.sub("", name).strip() or name, int(m.group(1))) if m else (name, None)


def norm_title(t):
    t = unicodedata.normalize("NFKC", t or "").lower()
    return " ".join(re.sub(r"[^\w]+", " ", t).split())


def season_numbers(t):
    """Season or part numbers in a title: '2', '2nd' and 'II' all count as 2 (1 says nothing)."""
    out = set()
    for w in norm_title(t).split():
        m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", w)
        if m:
            out.add(str(int(m.group(1))))
        elif w in ROMAN:
            out.add(ROMAN[w])
    return out - {"1"}


def title_likeness(a, b):
    """0..1. A name that is the start of the full title ('86' for '86 EIGHTY-SIX') counts as a good fit."""
    if not a or not b:
        return 0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if b.startswith(a + " "):
        r = max(r, .8 + .2 * len(a) / len(b))
    return r


SERIES_GENERIC = {"the", "and", "season", "seasons", "part", "cour", "stage", "final", "first", "second", "third", "fourth",
                  "fifth", "new", "series", "movie", "special", "specials", "chapter", "arc", "story", "end", "no", "wa", "tv"}


def same_series(a, b):
    """Whether two AniList titles name the same series. A prequel link can cross into another one
    (MF Ghost's prequel is Initial D Final Stage); those are kept apart."""
    names = lambda d: tuple(sorted({n for n in (norm_title(t) for t in d.values() if t) if n}))
    return _same_series(names(a), names(b))


@functools.lru_cache(maxsize=50000)
def _same_series(xs, ys):
    first = lambda t: next((w for w in t.split() if w not in ("the", "a", "an")), t)
    words = lambda t: [w for w in t.split() if len(w) >= 3 and w not in SERIES_GENERIC]
    for x in xs:
        for y in ys:
            if first(x) == first(y) or difflib.SequenceMatcher(None, x, y).ratio() >= .6:
                return True
            if any(u in v or v in u for u in words(x) for v in words(y)):   # 'monogatari' in 'nisemonogatari'
                return True
    return False


SAID = {"OVA": re.compile(r"\b(ova|oad|oav)\b", re.I), "SPECIAL": re.compile(r"\bspecials?\b", re.I), "MUSIC": re.compile(r"\b(music|pv)\b", re.I)}
SAID_ANY = re.compile("|".join(p.pattern for p in SAID.values()), re.I)   # a name that asks for an OVA, special or music video


def score_candidate(base, year, kind, cand, rank):
    """How well one AniList result fits a name: title likeness, then format, season number, year and AniList's own order."""
    n = norm_title(SAID_ANY.sub(" ", base)) or norm_title(base)   # "Toradora! OVA" is compared as "Toradora!"
    titles = [t for t in [cand["title"].get(k) for k in ("english", "romaji", "native")] + (cand.get("synonyms") or []) if t]
    sim, best = max(((title_likeness(n, norm_title(t)), t) for t in titles), default=(0, ""))
    s = sim - .03 * rank
    fmt = cand.get("format")
    if kind:
        s += .15 if fmt == kind else -.1
    elif MOVIE_WORDS.search(base):
        s += .12 if fmt == "MOVIE" else 0
    elif MINOR_WORDS.search(base):
        s += .05 if fmt in MINOR_FORMATS else 0
        if SAID_ANY.search(base):
            s += .1 if fmt in SAID and SAID[fmt].search(base) else 0 if fmt in MINOR_FORMATS else -.08   # the OVA over the special or the series
    else:
        s += FORMAT_PRIOR.get(fmt, 0)   # a plain name means the show itself, not its specials or shorts
    nn, tn = season_numbers(base), season_numbers(best)
    if nn or tn:
        s += .06 if nn == tn else -.12 if nn - tn else -.06
    cy = cand.get("seasonYear") or (cand.get("startDate") or {}).get("year")
    if year and cy:
        s += .25 if cy == year else -.2
    return s, sim


def pick_candidate(name, kind, cands):
    base, year = split_year(name)
    scored = [(score_candidate(base, year, kind, c, r), c) for r, c in enumerate(cands)]
    (_, sim), c = max(scored, key=lambda x: x[0][0])
    return c, sim


def cover_entry(media, sim, search="", manual=False):
    t = media["title"]
    return {"file": f'{media["id"]}.jpg', "id": media["id"], "url": media["coverImage"]["large"],
            "match": t.get("english") or t.get("romaji"), "fmt": media.get("format"),
            "year": media.get("seasonYear") or (media.get("startDate") or {}).get("year"),
            "conf": round(sim, 2), "search": search, "manual": manual, "v": MATCH_V}


def no_match(search=""):
    return {"file": None, "match": "", "search": search, "at": time.time(), "v": MATCH_V}


def ensure_image(ent):
    """Covers are downloaded the first time they're shown (a big import matches hundreds of shows at once)."""
    path = os.path.join(COVERS, ent["file"])
    if not os.path.exists(path):
        url = ent.get("url") or gql(ID_QUERY, {"id": ent["id"]})["coverImage"]["large"]
        img = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        data = urllib.request.urlopen(img, timeout=15).read()
        os.makedirs(COVERS, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return path


def fetch_cover(name, search=None, media_id=None, kind=None):
    """Find the AniList entry for a name. A typed search or a picked id is the user's choice and is kept as given."""
    if media_id:
        return cover_entry(gql(ID_QUERY, {"id": media_id}), 1.0, search or "", True)
    if search:
        try:
            return cover_entry(gql(QUERY, {"s": search}), 1.0, search, True)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return no_match(search)
            raise
    for term in search_terms(split_year(name)[0]):
        cands = gql(CAND_QUERY, {"s": term}, "Page")["media"]
        if cands:
            return cover_entry(*pick_candidate(name, kind, cands))
    return no_match()


def cover_retry(ent):
    """A title AniList didn't know (or that failed before this check existed) is looked up again after a while."""
    return (ent is not None and not ent.get("file") and not ent.get("manual")
            and (ent.get("v") != MATCH_V or time.time() - ent.get("at", 0) > NEG_RETRY))   # matching got better: ask again now


def cover_for(name):
    with cover_lock:
        db = load_covers()
        ent = db.get(name)
        if ent is None:   # "not found" entries are retried by the resolver, many per AniList call
            try:
                ent = fetch_cover(name)
            except Exception as e:
                print("cover lookup failed:", name, e)
                return None  # not cached: transient failures retry next load
            db[name] = ent
            save_covers(db)
        return ent


INFO_FIELDS = ("id idMal format status isAdult seasonYear startDate{year month day} genres synonyms averageScore description(asHtml:false) "
               "title{romaji english native} tags{name rank isGeneralSpoiler isMediaSpoiler}")
INFO_QUERY = "query($id:Int){Media(id:$id){" + INFO_FIELDS + "}}"
INFO_DB = os.path.join(ROOT, "data", "info.json")
INFO_TTL = 30 * 24 * 3600
UNRELEASED_TTL = 12 * 3600   # a show that hasn't started airing changes status the day it premieres
info_lock = threading.Lock()
jikan_lock = threading.Lock()
# MyAnimeList's age ratings (via Jikan), shortened for the cards. Order matters: first prefix wins.
RATINGS = [("G ", "G"), ("PG - ", "PG"), ("PG-13", "PG-13"), ("R - 17", "R-17+"), ("R+", "R+"), ("Rx", "Rx")]
UNCENSORED_RE = re.compile(r"uncensor|unrated", re.I)


class JikanDown(Exception):
    """MyAnimeList's API is failing or refusing us; stop asking for a while."""


JIKAN_GAP = 1.5            # seconds between calls: at most 40 a minute, under Jikan's 60
JIKAN_PAUSE = 30 * 60      # after any failure, no calls at all for this long
RATING_RETRY = 24 * 3600   # a title whose rating could not be fetched waits this long
jikan_pause_until = [0.0]
rating_queue = []          # media ids waiting for a rating; one worker drains it
rating_worker = [None]


def jikan_data(mal_id):
    """MyAnimeList's facts for a show: age rating text ('R+ - Mild Nudity'), score, rank, popularity; None if MAL has none.
    Raises JikanDown on any failure and then makes no more calls for JIKAN_PAUSE."""
    with jikan_lock:
        if time.time() < jikan_pause_until[0]:
            raise JikanDown("paused")
        time.sleep(JIKAN_GAP)
        req = urllib.request.Request(f"https://api.jikan.moe/v4/anime/{mal_id}", headers={"User-Agent": "anime-list"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=6))["data"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            pause = float(e.headers.get("Retry-After") or 0) if e.code == 429 else 0
            jikan_pause_until[0] = time.time() + max(JIKAN_PAUSE, pause)
            raise JikanDown(str(e))
        except (OSError, ValueError) as e:
            jikan_pause_until[0] = time.time() + JIKAN_PAUSE
            raise JikanDown(str(e))


def rating_code(text, adult):
    code = next((c for pre, c in RATINGS if text and text.startswith(pre)), "")
    if not code and adult:
        return "Rx", "Adult (AniList)"
    return code, text or ""


def load_info():
    try:
        with open(INFO_DB) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_info(db):
    with open(INFO_DB, "w") as f:
        json.dump(db, f, indent=1)


def mal_done(ent):
    """Nothing more to ask MAL: rating and score/rank/popularity are all saved (or there is no MAL entry)."""
    return bool(ent.get("rated") and ("mal_score" in ent or not ent.get("mal")))


def fetch_rating(media_id):
    """Ask MAL for one title's rating, score, rank and popularity and save them. Failures are remembered so we don't retry soon."""
    with info_lock:
        ent = load_info().get(str(media_id))
    if not ent or mal_done(ent):
        return
    try:
        data = (jikan_data(ent["mal"]) if ent.get("mal") else None) or {}
        text = data.get("rating")
        failed = False
    except JikanDown as e:
        if str(e) == "paused":
            return   # nothing was asked; it gets queued again after the pause
        text, failed = None, True
    with info_lock:
        db = load_info()
        ent = db.get(str(media_id))
        if not ent:
            return
        if failed:
            ent["rating_try"] = time.time()
        else:
            code, shown = rating_code(text, ent.get("adult"))
            ent.update(rating=code, ratingText=shown, rated=True)
            if ent.get("mal"):
                ent.update(mal_score=data.get("score"), mal_rank=data.get("rank"), mal_pop=data.get("popularity"))
        save_info(db)


def drain_ratings():
    while True:
        with info_lock:
            if not rating_queue:
                rating_worker[0] = None
                return
            media_id = rating_queue.pop(0)
        try:
            fetch_rating(media_id)
        except Exception as e:
            print("rating lookup failed:", media_id, e)


def want_rating(media_id):
    """Queue a rating lookup (once per title), unless the last try failed recently."""
    with info_lock:
        ent = load_info().get(str(media_id))
        if (not ent or mal_done(ent) or media_id in rating_queue
                or time.time() - ent.get("rating_try", 0) < RATING_RETRY
                or time.time() < jikan_pause_until[0]):
            return
        rating_queue.append(media_id)
        if rating_worker[0] is None:
            rating_worker[0] = threading.Thread(target=drain_ratings, daemon=True)
            rating_worker[0].start()


def build_info(media_id):
    """Everything AniList knows; the age rating comes later from MAL, in the background."""
    return info_from(gql(INFO_QUERY, {"id": media_id}))


def info_stale(ent):
    return (not ent or "format" not in ent or "desc" not in ent or "al_score" not in ent or "titles" not in ent or "status" not in ent
            or time.time() - ent["at"] > (UNRELEASED_TTL if ent.get("status") == "NOT_YET_RELEASED" else INFO_TTL))


def keep_mal(fresh, old):
    """A refreshed entry keeps the MAL facts already fetched for it."""
    if old.get("rated") and fresh.get("mal") == old.get("mal"):
        fresh.update({k: old[k] for k in ("rating", "ratingText", "rated", "mal_score", "mal_rank", "mal_pop") if k in old})
    return fresh


def info_from(m):
    names = list(m["title"].values()) + (m["synonyms"] or [])
    tags = sorted((t for t in m["tags"] if t["rank"] >= 60 and not t["isGeneralSpoiler"] and not t["isMediaSpoiler"]),
                  key=lambda t: -t["rank"])
    code, text = rating_code(None, m["isAdult"])
    return {"format": m["format"], "status": m["status"], "start": m["startDate"],
            "year": m["seasonYear"] or (m["startDate"] or {}).get("year"),
            "rating": code, "ratingText": text, "mal": m.get("idMal"), "adult": m["isAdult"],
            "rated": not m.get("idMal"),   # nothing to ask MAL about without an id
            "desc": tidy_description(m.get("description")),
            "al_score": m.get("averageScore"),
            "titles": {"en": m["title"].get("english") or m["title"]["romaji"], "ro": m["title"]["romaji"],
                       "jp": m["title"].get("native") or m["title"]["romaji"]},
            "uncensored": any(UNCENSORED_RE.search(n or "") for n in names),
            "tags": list(dict.fromkeys(m["genres"] + [t["name"] for t in tags[:8]]))}


def info_for(name):
    """Saved facts are served at once; MAL is only asked for a missing rating, in the background."""
    cover = cover_for(name)
    if not cover or not cover["file"]:
        return None
    media_id = cover.get("id") or int(cover["file"].split(".")[0])
    with info_lock:
        ent = load_info().get(str(media_id))
    if ent and "rated" not in ent:
        # Saved by an older version. A complete one keeps its rating; one that never got a rating
        # lacks the MAL id, so its facts are fetched once more.
        if ent.get("partial") is False:
            ent["rated"] = True
        else:
            ent = None
    if info_stale(ent):
        try:
            fresh = {"at": time.time(), **build_info(media_id)}
        except Exception:
            if not ent:
                raise
            fresh = None   # AniList is down: show what we have
        if fresh:
            with info_lock:
                db = load_info()
                db[str(media_id)] = ent = keep_mal(fresh, db.get(str(media_id)) or {})
                save_info(db)
    want_rating(media_id)
    return ent


def episode_count(node):
    """Episodes out so far: for an airing show that's one before the next to air.
    A part that hasn't started, or is airing with no schedule, has only a planned total: not episodes you can watch."""
    nxt = node.get("nextAiringEpisode")
    if nxt:
        return nxt["episode"] - 1
    if node.get("status") in ("NOT_YET_RELEASED", "RELEASING"):
        return None
    return node["episodes"] or None


def build_seasons(media_id, nodes=None):
    """Walk AniList's prequel/sequel links to list a series' TV seasons in order. `nodes` may hold entries already fetched."""
    nodes = {} if nodes is None else nodes

    def node(i):
        if i not in nodes:
            nodes[i] = gql(SEASON_QUERY, {"id": i})
        return nodes[i]

    def step(i, kind, seen):
        """The next season along `kind` links, passing through up to two movies or OVAs
        (Initial D goes Second Stage, Third Stage the movie, Fourth Stage)."""
        for _ in range(3):
            n = node(i)
            rel = [(e["node"]["id"], e["node"]["format"]) for e in n["relations"]["edges"]
                   if e["relationType"] == kind and e["node"]["id"] not in seen and same_series(n["title"], e["node"].get("title") or {})]
            hit = [x for x, f in rel if f in SEASON_FORMATS]
            if hit:
                return hit[0]
            via = [x for x, f in rel if f in BRIDGE_FORMATS]
            if not via:
                return None
            i = via[0]
            seen.add(i)
        return None

    cur, back = media_id, {media_id}
    for _ in range(12):
        pre = step(cur, "PREQUEL", back)
        if pre is None:
            break
        cur = pre
        back.add(cur)
    chain, seen = [cur], {cur}
    for _ in range(15):
        nxt = step(chain[-1], "SEQUEL", seen)
        if nxt is None:
            break
        chain.append(nxt)
        seen.add(nxt)
    # AniList files each cour as its own entry; fold "Part 2" / "Cour 2" into the season before it.
    groups = []
    for i in chain:
        m = nodes[i]
        title = m["title"].get("english") or m["title"].get("romaji")
        if groups and re.search(r"\b(part|cour)\s*[2-9]\b|second half|2nd cour", title, re.I):
            groups[-1]["parts"].append({"id": i, "episodes": episode_count(m)})
        else:
            groups.append({"title": title, "ro": m["title"].get("romaji") or title, "jp": m["title"].get("native") or title,
                           "parts": [{"id": i, "episodes": episode_count(m)}]})
    out = []
    for n, g in enumerate(groups, 1):
        known = [p["episodes"] for p in g["parts"] if p["episodes"] is not None]  # unreleased parts count as 0
        nxt = [nodes[p["id"]]["nextAiringEpisode"] for p in g["parts"] if nodes[p["id"]].get("nextAiringEpisode")]
        out.append({"n": n, "title": g["title"], "ro": g["ro"], "jp": g["jp"], "parts": g["parts"],
                    "next": {"episode": nxt[0]["episode"], "at": nxt[0]["airingAt"]} if nxt else None,
                    "cover": nodes[g["parts"][0]["id"]]["coverImage"]["large"],
                    "episodes": sum(known) if known else None,
                    "airing": any(nodes[p["id"]].get("nextAiringEpisode") for p in g["parts"])})
    return out


GROUP_RELS = ("PARENT", "SIDE_STORY", "SPIN_OFF", "SUMMARY", "COMPILATION", "PREQUEL", "SEQUEL")


def related_ids(media_id, nodes):
    """Entries an OVA, movie or special hangs off (its parent series, side stories), so the page can put it on that show's card."""
    n = nodes.get(media_id)
    if not n:
        return []
    return [e["node"]["id"] for e in n["relations"]["edges"]
            if e["relationType"] in GROUP_RELS and same_series(n["title"], e["node"].get("title") or {})]


def seasons_fresh(ent):
    if not ent or ent.get("v") != SEASONS_V:
        return False  # older saves counted planned episodes as released
    if not all("cover" in x for x in ent["seasons"]) or any(x.get("airing") and "next" not in x for x in ent["seasons"]):
        return False  # cached before covers / air dates were stored
    airing = any(x.get("airing", True) for x in ent["seasons"])
    next_aired = any(x.get("next") and x["next"]["at"] < time.time() for x in ent["seasons"])
    return not next_aired and time.time() - ent["at"] < (AIRING_TTL if airing else SEASONS_TTL)


def seasons_for(name):
    with seasons_lock:
        try:
            with open(SEASONS_DB) as f:
                db = json.load(f)
        except FileNotFoundError:
            db = {}
        ent = db.get(name)
        if seasons_fresh(ent):
            return ent["seasons"]
        cover = cover_for(name)
        if not cover or not cover["file"]:
            return None
        media_id = cover.get("id") or int(cover["file"].split(".")[0])
        nodes = {}
        seasons = build_seasons(media_id, nodes)
        db[name] = {"at": time.time(), "v": SEASONS_V, "seasons": seasons, "rel": related_ids(media_id, nodes)}
        with open(SEASONS_DB, "w") as f:
            json.dump(db, f, indent=1)
        return seasons


def forget_seasons(name):
    with seasons_lock:
        try:
            with open(SEASONS_DB) as f:
                db = json.load(f)
        except FileNotFoundError:
            return
        if db.pop(name, None) is not None:
            with open(SEASONS_DB, "w") as f:
                json.dump(db, f, indent=1)


def image_for(url):
    """Download a user-supplied cover URL once; returns (path, content type)."""
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("cover must be an http(s) URL")
    os.makedirs(COVERS, exist_ok=True)
    base = os.path.join(COVERS, "u-" + hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(base):
        with open(base + ".type") as f:
            return base, f.read()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=15) as r:
        ctype = r.headers.get_content_type()
        if not ctype.startswith("image/"):
            raise ValueError("that URL is not an image")
        data = r.read(15_000_000)
    with open(base, "wb") as f:
        f.write(data)
    with open(base + ".type", "w") as f:
        f.write(ctype)
    return base, ctype


search_cache = {}


def search_titles(q):
    """AniList title suggestions for the add box (cached per query)."""
    q = q.strip().lower()
    if len(q) < 2:
        return []
    if q not in search_cache:
        media = gql(SEARCH_QUERY, {"s": q}, "Page")["media"]
        search_cache[q] = [{"id": m["id"], "format": m["format"], "year": m["seasonYear"],
                            "title": m["title"].get("english") or m["title"]["romaji"],
                            "cover": m["coverImage"]["medium"]} for m in media]
        if len(search_cache) > 200:
            search_cache.pop(next(iter(search_cache)))
    return search_cache[q]


DISCOVER_DB = os.path.join(ROOT, "data", "discover.json")
DISCOVER_QUERY = """query($season:MediaSeason,$year:Int,$page:Int){Page(page:$page,perPage:50){pageInfo{hasNextPage}
  media(season:$season,seasonYear:$year,type:ANIME,isAdult:false,format_in:[TV,TV_SHORT,MOVIE,ONA,OVA],sort:POPULARITY_DESC){
  id format episodes duration status averageScore popularity genres description(asHtml:false)
  studios(isMain:true){nodes{name}} coverImage{extraLarge} title{romaji english native}
  startDate{year month day} nextAiringEpisode{episode airingAt}}}}"""
SEASONS = ("WINTER", "SPRING", "SUMMER", "FALL")
discover_lock = threading.Lock()


def tidy_description(text):
    """AniList synopses come with <br> and <i> tags; return plain text of about 420 characters."""
    text = re.sub(r"<br\s*/?>", " ", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 420:
        text = text[:420].rsplit(" ", 1)[0].rstrip(",.;: ") + "…"
    return text


def discover(season, year):
    """Every show of one season (several AniList pages, saved on disk; stale copy used if AniList is down)."""
    key = f"{season}-{year}"
    with discover_lock:
        try:
            with open(DISCOVER_DB, encoding="utf-8") as f:
                db = json.load(f)
        except FileNotFoundError:
            db = {}
        ent = db.get(key)
        # A season still running changes by the hour (new episodes), a finished one hardly at all.
        ttl = 3 * 3600 if year * 4 + SEASONS.index(season) >= time.localtime().tm_year * 4 + (time.localtime().tm_mon - 1) // 3 - 1 else 7 * 24 * 3600
        if ent and time.time() - ent["at"] < ttl and all("ro" in x for x in ent["shows"][:1]):   # older saves lack the other titles
            return ent
        shows = []
        try:
            for page in range(1, 5):
                data = gql(DISCOVER_QUERY, {"season": season, "year": year, "page": page}, "Page")
                for m in data["media"]:
                    t = m["title"]
                    nxt = m.get("nextAiringEpisode")
                    shows.append({"id": m["id"], "title": t.get("english") or t["romaji"], "ro": t["romaji"], "jp": t.get("native") or t["romaji"], "format": m["format"],
                                  "episodes": m["episodes"], "duration": m["duration"], "status": m["status"],
                                  "score": m["averageScore"], "popularity": m["popularity"], "genres": m["genres"],
                                  "studio": (m["studios"]["nodes"] or [{}])[0].get("name", ""),
                                  "cover": m["coverImage"]["extraLarge"], "desc": tidy_description(m["description"]),
                                  "start": m["startDate"], "next": {"episode": nxt["episode"], "at": nxt["airingAt"]} if nxt else None})
                if not data["pageInfo"]["hasNextPage"]:
                    break
        except Exception:
            if ent:
                return ent   # AniList is down: show what we saved
            raise
        ent = {"at": time.time(), "shows": shows}
        db[key] = ent
        with open(DISCOVER_DB, "w", encoding="utf-8") as f:
            json.dump(db, f)
        return ent


# ---- Calendar: what airs in a week (AniList's real schedule, not a projection).
CAL_DB = os.path.join(ROOT, "data", "calendar.json")
CAL_QUERY = """query($from:Int,$to:Int,$page:Int){Page(page:$page,perPage:50){pageInfo{hasNextPage}
  airingSchedules(airingAt_greater:$from,airingAt_lesser:$to,sort:TIME){airingAt episode
  media{id format episodes isAdult popularity title{romaji english native} coverImage{large}}}}}"""
cal_lock = threading.Lock()


def calendar(start, days=7):
    """Episodes airing from `start` (unix seconds) for `days` days. Saved on disk; a stale copy is used if AniList is down."""
    key = f"{start}-{days}"
    with cal_lock:
        try:
            with open(CAL_DB, encoding="utf-8") as f:
                db = json.load(f)
        except (FileNotFoundError, ValueError):
            db = {}
        ent = db.get(key)
        # this week and later change as schedules are published; a past week never changes
        ttl = 3600 if start + days * 86400 > time.time() else 30 * 24 * 3600
        if ent and time.time() - ent["at"] < ttl and all("ro" in x for x in ent["items"][:1]):   # older saves lack the other titles
            return ent
        rows = []
        try:
            for page in range(1, 11):
                data = gql(CAL_QUERY, {"from": start - 1, "to": start + days * 86400, "page": page}, "Page")
                for r in data["airingSchedules"]:
                    m = r["media"]
                    if m["isAdult"] or m["format"] not in ("TV", "TV_SHORT", "MOVIE", "ONA", "OVA"):
                        continue
                    t = m["title"]
                    rows.append({"id": m["id"], "title": t.get("english") or t["romaji"], "ro": t["romaji"], "jp": t.get("native") or t["romaji"], "cover": m["coverImage"]["large"],
                                 "at": r["airingAt"], "ep": r["episode"], "eps": m["episodes"], "format": m["format"], "pop": m["popularity"]})
                if not data["pageInfo"]["hasNextPage"]:
                    break
        except Exception:
            if ent:
                return ent
            raise
        ent = {"at": time.time(), "items": rows}
        db[key] = ent
        for k in [k for k, v in db.items() if time.time() - v["at"] > 60 * 24 * 3600]:   # forget very old weeks
            del db[k]
        with open(CAL_DB, "w", encoding="utf-8") as f:
            json.dump(db, f)
        return ent


# ---- Watch log: one line each time progress or status changes, so a year-in-review can exist. Never read by the list itself.
HISTORY_DB = os.path.join(ROOT, "data", "history.json")
history_lock = threading.Lock()


def import_history(events, replace):
    """Watch dates from an Anime-Planet or MyAnimeList export. For the `replace` names, the entries made when they were
    first added (which older imports logged as watched that day) give way to the export's real dates."""
    now, keep = time.time() + 86400, set(replace)
    clean = []
    for e in events[:50000]:
        t = int(e.get("t", 0))
        if not 631152000 <= t <= now or e.get("status") not in STATUS_LABELS:   # 1990 to today
            continue
        clean.append({"t": t, "name": str(e.get("name", ""))[:300], "from": str(e.get("from", ""))[:20], "to": str(e.get("to", ""))[:20],
                      "was": e.get("was") if e.get("was") in STATUS_LABELS else "", "status": e["status"]})
    with history_lock:
        try:
            with open(HISTORY_DB, encoding="utf-8") as f:
                log = json.load(f)
        except (FileNotFoundError, ValueError):
            log = []
        log = [e for e in log if not (e["name"] in keep and not e.get("from") and not e.get("was"))]
        seen = {(e["t"], e["name"], e["to"], e["status"]) for e in log}
        log += [e for e in clean if (e["t"], e["name"], e["to"], e["status"]) not in seen]
        log.sort(key=lambda e: e["t"])
        with open(HISTORY_DB, "w", encoding="utf-8") as f:
            json.dump(log[-30000:], f)
    return len(clean)


def log_history(old, new, quiet=()):
    """Note what moved since the last save. `quiet` names were just imported: what they say was watched happened
    before today, so it isn't logged as today (an import's own dates come in through import_history)."""
    before = {i["name"]: i for i in old}
    now = int(time.time())
    events = []
    for it in new:
        if it["name"] in quiet:
            continue
        o = before.get(it["name"])
        if o and o["progress"] == it["progress"] and o["status"] == it["status"]:
            continue
        if not o and not it["progress"] and it["status"] == "not started":
            continue   # just added, nothing watched yet
        events.append({"t": now, "name": it["name"], "from": o["progress"] if o else "", "to": it["progress"],
                       "was": o["status"] if o else "", "status": it["status"]})
    if not events:
        return
    with history_lock:
        try:
            with open(HISTORY_DB, encoding="utf-8") as f:
                log = json.load(f)
        except (FileNotFoundError, ValueError):
            log = []
        log = (log + events)[-30000:]
        with open(HISTORY_DB, "w", encoding="utf-8") as f:
            json.dump(log, f)


# ---- Self-update from GitHub Releases. Only the app files are replaced; data/ is never touched.
UPDATE_REPO = "Obscuratea/animus-obscurus"
UPDATE_API = os.environ.get("ANIMUS_UPDATE_API") or f"https://api.github.com/repos/{UPDATE_REPO}/releases/latest"
UPDATE_FILES = ("server.py", "index.html", "template/Anime Watch List.xlsx", "CHANGELOG.txt")
UPDATE_EVERY = 24 * 3600
update_lock = threading.Lock()
update_state = {"at": 0, "latest": "", "notes": "", "zip": "", "sha": "", "error": ""}
SERVER = None


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4])


def check_update():
    """Ask GitHub for the newest release. Needs no login; a private or missing repo just means no update."""
    with update_lock:
        st = update_state
        st["at"] = time.time()
        try:
            req = urllib.request.Request(UPDATE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "animus-obscurus"})
            with urllib.request.urlopen(req, timeout=15) as r:
                rel = json.load(r)
            tag = str(rel.get("tag_name", "")).lstrip("vV")
            zips = [a for a in rel.get("assets", []) if re.fullmatch(r"Animus-Obscurus-Update-v[\d.]+\.zip", a.get("name", ""))]
            sums = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
            st.update(error="", latest=tag, notes=str(rel.get("body") or ""), zip="", sha="")
            if tag and zips and zips[0]["name"] + ".sha256" in sums:
                st.update(zip=zips[0]["browser_download_url"], sha=sums[zips[0]["name"] + ".sha256"])
        except urllib.error.HTTPError as e:
            st.update(latest="", zip="", error="no releases found" if e.code == 404 else f"GitHub said {e.code}")
        except Exception as e:
            st.update(latest="", zip="", error="couldn't reach GitHub")
        return st


def update_info():
    st = update_state
    avail = bool(st["latest"] and st["zip"] and vtuple(st["latest"]) > vtuple(VERSION))
    return {"current": VERSION, "latest": st["latest"], "available": avail, "notes": st["notes"] if avail else "",
            "auto": read_settings().get("autoupdate", True), "checked": int(st["at"]), "error": st["error"]}


def update_loop():
    while True:
        if read_settings().get("autoupdate", True) and time.time() - update_state["at"] > UPDATE_EVERY:
            check_update()
        time.sleep(3600)


def fetch_bytes(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": "animus-obscurus"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise ValueError("download is too big")
    return data


def apply_update():
    """Download, verify and install the update zip, keeping a rollback copy. Returns the new version."""
    st = update_state
    if os.path.exists(os.path.join(ROOT, ".git")):
        raise ValueError("this is a git working copy; it is changed with git, not the updater")
    if not update_info()["available"]:
        raise ValueError("no update available")
    for u in (st["zip"], st["sha"]):
        if not u.startswith("https://") and not os.environ.get("ANIMUS_UPDATE_API"):
            raise ValueError("update address is not https")
    blob = fetch_bytes(st["zip"], 60_000_000)
    want = fetch_bytes(st["sha"], 4096).decode("ascii", "replace").split()
    if not want or hashlib.sha256(blob).hexdigest() != want[0].lower():
        raise ValueError("the download didn't match its checksum, so nothing was changed")
    z = zipfile.ZipFile(io.BytesIO(blob))
    files = {}
    for name in z.namelist():
        parts = name.split("/", 1)
        rel = parts[1] if len(parts) == 2 else ""
        if rel in UPDATE_FILES:
            files[rel] = z.read(name)
    if "server.py" not in files or "index.html" not in files:
        raise ValueError("that isn't an Animus update")
    compile(files["server.py"], "server.py", "exec")
    m = re.search(rb'^VERSION = "([^"]+)"', files["server.py"], re.M)
    if not m or vtuple(m.group(1).decode()) <= vtuple(VERSION):
        raise ValueError("the update isn't newer than this copy")
    back = os.path.join(ROOT, ".update-backup")
    shutil.rmtree(back, ignore_errors=True)
    done = []
    try:
        for rel, data in files.items():
            dest = os.path.join(ROOT, *rel.split("/"))
            if os.path.exists(dest):
                os.makedirs(os.path.dirname(os.path.join(back, *rel.split("/"))), exist_ok=True)
                shutil.copy2(dest, os.path.join(back, *rel.split("/")))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = dest + ".new"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            done.append(rel)
    except Exception:
        for rel in done:   # put the old files back
            old = os.path.join(back, *rel.split("/"))
            if os.path.exists(old):
                shutil.copy2(old, os.path.join(ROOT, *rel.split("/")))
        raise
    return m.group(1).decode()


RESTART = False


def restart_soon():
    """Let the reply reach the page, then stop serving; the main thread starts the new server.py."""
    global RESTART
    RESTART = True
    def go():
        time.sleep(0.8)
        SERVER.shutdown()
    threading.Thread(target=go, daemon=True).start()


def relaunch():
    SERVER.server_close()
    args = [sys.executable, os.path.join(ROOT, "server.py")] + [a for a in sys.argv[1:] if a != "--open"]
    if os.name == "nt":
        import subprocess
        subprocess.Popen(args, cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
        os._exit(0)
    os.chdir(ROOT)
    os.execv(sys.executable, args)


def changelog_text():
    """The file keeps every release; the "What's new" window only gets the newest few."""
    full = changelog_file()
    if not full:
        return full
    parts = re.split(r"(?m)^(?=## )", full)   # the title, then one chunk per release
    return "".join(parts[:1 + CHANGELOG_SHOWN])


CHANGELOG_SHOWN = 5


def changelog_file():
    for name in ("CHANGELOG.md", "CHANGELOG.txt"):
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
    return None


FRIENDS = os.path.join(ROOT, "data", "friends.json")
friends_lock = threading.Lock()


def load_friends():
    try:
        with open(FRIENDS, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def cover_url_for(name, media_id):
    """AniList's cover URL for a title: from the seasons cache when possible, else one lookup."""
    try:
        with open(SEASONS_DB) as f:
            seasons = json.load(f).get(name, {}).get("seasons") or []
        if seasons and seasons[0].get("cover"):
            return seasons[0]["cover"]
    except FileNotFoundError:
        pass
    try:
        return gql("query($id:Int){Media(id:$id){coverImage{large}}}", {"id": media_id})["coverImage"]["large"]
    except Exception:
        return ""


def export_recs():
    me = read_settings().get("me") or "A friend"
    out = []
    for it in read_items():
        if not it["rec"]:
            continue
        cover = cover_for(it["name"])
        media_id = (cover or {}).get("id") or (int(cover["file"].split(".")[0]) if cover and cover.get("file") else None)
        with info_lock:
            info = load_info().get(str(media_id)) or {} if media_id else {}
        out.append({"name": it["name"], "id": media_id, "year": info.get("year"), "rating": it["rating"],
                    "cover": cover_url_for(it["name"], media_id) if media_id else ""})
    return me, {"app": "animus-recs", "v": 1, "from": me, "items": out}


def import_recs(doc, code=None):
    """Keep a friend's exported list (replacing their earlier one). Everything in it is treated as untrusted text.
    `code` is the friend's live share id, kept so their list can be refreshed later."""
    if not isinstance(doc, dict) or doc.get("app") != "animus-recs" or not isinstance(doc.get("items"), list):
        raise ValueError("that isn't an Animus recommendations file")
    who = str(doc.get("from") or "A friend").strip()[:40] or "A friend"
    items = []
    for m in doc["items"][:300]:
        name = str(m.get("name", "")).strip()[:200]
        if not name:
            continue
        cover = str(m.get("cover") or "")
        items.append({"name": name,
                      "id": m["id"] if isinstance(m.get("id"), int) else None,
                      "year": m["year"] if isinstance(m.get("year"), int) else None,
                      "rating": clean_rating(m.get("rating", "")),
                      "cover": cover if urlparse(cover).scheme in ("http", "https") else ""})
    with friends_lock:
        db = load_friends()
        for old in [k for k in db if k.lower() == who.lower()]:
            del db[old]   # "sam" and "Sam" are the same friend: their new list replaces the old one
        if code:
            for old in [k for k, v in db.items() if v.get("code") == code]:
                del db[old]   # the same person under a new name
        db[who] = {"at": time.time(), "items": items}
        if code:
            db[who]["code"] = code
        with open(FRIENDS, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=1)
    return who, len(items)


# ---- Live sharing through a small relay (see relay/). Opt-in; only the recommendations are ever sent. ----
RELAY_DEFAULT = "https://animus-relay.joshua-waguespack10.workers.dev"   # address of the deployed relay; ANIMUS_RELAY or settings "relay" override it
RELAY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,40}$")
relay_state = {"err": "", "pushed": 0, "hash": "", "wake": threading.Event()}


def relay_url():
    return (os.environ.get("ANIMUS_RELAY") or read_settings().get("relay") or RELAY_DEFAULT).rstrip("/")


def write_settings(cur):
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=1)


def relay_call(method, rid, body=None, key=None):
    url = relay_url()
    if not url:
        raise ValueError("live sharing isn't switched on in this version yet")
    headers = {"User-Agent": "animus-obscurus", "Content-Type": "application/json"}
    if key:
        headers["X-Key"] = key
    req = urllib.request.Request(f"{url}/r/{rid}", data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read(1_000_000)
    except urllib.error.HTTPError as e:
        raise ValueError({404: "nobody is sharing with that code (they may have turned it off)",
                          403: "the sharing service refused this", 413: "your list is too big to share"}.get(e.code, f"the sharing service answered {e.code}"))
    except (urllib.error.URLError, OSError):
        raise ValueError("couldn't reach the sharing service")


def parse_code(text):
    rid = re.sub(r"\s+", "", str(text))
    rid = rid[7:] if rid.lower().startswith("animus:") else rid
    if not RELAY_ID_RE.match(rid):
        raise ValueError("that doesn't look like an Animus share code")
    return rid


def relay_status():
    s = read_settings()
    return {"ready": bool(relay_url()), "sharing": bool(s.get("share")), "me": s.get("me", ""),
            "code": "animus:" + s["relay_id"] if s.get("share") and s.get("relay_id") else "",
            "error": relay_state["err"], "pushed": relay_state["pushed"]}


def relay_push(force=False):
    """Send my recommendations when they changed (or once a day, so the relay keeps them)."""
    s = read_settings()
    if not s.get("share") or not s.get("relay_id"):
        return False
    _, doc = export_recs()
    body = json.dumps(doc, separators=(",", ":")).encode()
    h = hashlib.sha256(body).hexdigest()
    if not force and h == relay_state["hash"] and time.time() - relay_state["pushed"] < 86400:
        return False
    relay_call("PUT", s["relay_id"], body, s["relay_key"])
    relay_state.update(hash=h, pushed=time.time(), err="")
    return True


def relay_set_sharing(on, reset=False):
    s = read_settings()
    if (not on or reset) and s.get("relay_id"):
        try:
            relay_call("DELETE", s["relay_id"], key=s["relay_key"])
        except ValueError:
            pass   # already gone, or unreachable: forgetting the code locally is what matters
        s.pop("relay_id", None); s.pop("relay_key", None)
    if on:
        if not s.get("me"):
            raise ValueError("set your name first, so friends can see who is sharing")
        if not s.get("relay_id"):
            s["relay_id"], s["relay_key"] = secrets.token_urlsafe(16), secrets.token_urlsafe(24)
    s["share"] = bool(on)
    write_settings(s)
    if on:
        try:
            relay_push(force=True)
        except ValueError:
            s["share"] = False
            write_settings(s)
            raise


def relay_follow(code_text):
    rid = parse_code(code_text)
    if rid == read_settings().get("relay_id"):
        raise ValueError("that's your own code")
    return import_recs(json.loads(relay_call("GET", rid)), rid)


def relay_refresh():
    """Re-read every friend that was added by code. Returns (how many updated, problems)."""
    done, problems = 0, []
    for who, v in list(load_friends().items()):
        if not v.get("code"):
            continue
        try:
            import_recs(json.loads(relay_call("GET", v["code"])), v["code"])
            done += 1
        except ValueError as e:
            problems.append(f"{who}: {e}")
    return done, problems


def relay_loop():
    relay_state["wake"].set()
    last_pull = 0
    while True:
        woke = relay_state["wake"].wait(1800)
        if woke:
            time.sleep(15)   # let a burst of edits settle
            relay_state["wake"].clear()
        if not relay_url():
            continue
        try:
            relay_push()
            if time.time() - last_pull > 3 * 3600:
                last_pull = time.time()
                relay_refresh()
        except Exception as e:
            relay_state["err"] = str(e)


# ---- The resolver: matches, season chains and details for the whole list in the background, many shows per AniList call.
resolve_state = {"running": False, "phase": "", "done": 0, "total": 0, "error": "", "wake": threading.Event()}


def gql_batch(field, keys, size):
    """Many lookups in one AniList call (aliases a0, a1, ...). Halves the batch if AniList finds it too big."""
    out, i = {}, 0
    while i < len(keys):
        chunk = keys[i:i + size]
        try:
            data = gql("query{" + " ".join(f"a{j}:{field(k)}" for j, k in enumerate(chunk)) + "}", {}, None)
        except urllib.error.HTTPError as e:
            if e.code in (400, 413) and size > 1:
                size = max(1, size // 2)
                continue
            raise
        for j, k in enumerate(chunk):
            out[k] = data.get(f"a{j}")
        i += len(chunk)
    return out


def needs_match(ent):
    if ent is None:
        return True
    if ent.get("manual") or ent.get("ok"):
        return False
    return cover_retry(ent) if not ent.get("file") else ent.get("v") != MATCH_V


def replaces_old(name, old, new, cands, kind=None):
    """An older automatic match is only swapped when it was clearly a side entry (special, OVA, short) and the name doesn't
    ask for one, or when today's matching rates the new pick higher on both title and overall fit (Frieren's chibi shorts
    are filed as an ONA, so the side-entry rule alone kept that old pick)."""
    was = next((c for c in cands if c["id"] == old.get("id")), None)
    if not was:
        return False   # the old pick isn't among today's results: nothing to compare it with
    base, year = split_year(name)
    rank = {c["id"]: r for r, c in enumerate(cands)}
    (s_new, sim_new), (s_old, sim_old) = (score_candidate(base, year, kind, x, rank[x["id"]]) for x in (new, was))
    if s_new > s_old and sim_new >= sim_old:
        return True
    if MINOR_WORDS.search(name) or MOVIE_WORDS.search(name):
        return False
    return was.get("format") in MINOR_FORMATS and new.get("format") in ("TV", "MOVIE", "ONA")


def resolve_matches(names, kinds, covers):
    resolve_state.update(phase="Finding your shows", total=len(names), done=0)
    search = lambda term: f"Page(perPage:8){{media(search:{json.dumps(term)},type:ANIME,sort:SEARCH_MATCH){{{CAND_FIELDS}}}}}"
    pending = [[n, search_terms(split_year(n)[0]), 0] for n in names]
    while pending:
        batch, pending = pending[:20], pending[20:]
        res = gql_batch(search, list(dict.fromkeys(p[1][p[2]] for p in batch)), 20)
        updates = {}
        for p in batch:
            name, terms, i = p
            cands = (res.get(terms[i]) or {}).get("media") or []
            if not cands and i + 1 < len(terms):
                p[2] += 1
                pending.append(p)   # try the looser spelling later
                continue
            old = covers.get(name)
            if not cands:
                updates[name] = old if old and old.get("file") else no_match()
            else:
                c, sim = pick_candidate(name, kinds.get(name), cands)
                new = cover_entry(c, sim)
                if old and old.get("file") and old.get("id") != c["id"] and not replaces_old(name, old, c, cands, kinds.get(name)):
                    was = next((x for x in cands if x["id"] == old.get("id")), None)
                    new = dict(old, v=MATCH_V)   # keep what was there; just note what it is
                    if was:
                        new.update(fmt=was.get("format"), year=was.get("seasonYear") or (was.get("startDate") or {}).get("year"),
                                   conf=round(score_candidate(*split_year(name), kinds.get(name), was, 0)[1], 2))
                updates[name] = new
            resolve_state["done"] += 1
        moved = []
        with cover_lock:
            db = load_covers()
            for name, ent in updates.items():
                cur = db.get(name)
                if cur is not None and (cur.get("manual") or cur.get("ok")):
                    continue   # picked by hand while we were busy
                if cur and cur.get("id") != ent.get("id"):
                    moved.append(name)
                db[name] = covers[name] = ent
            save_covers(db)
        for name in moved:
            forget_seasons(name)


def resolve_seasons(names, covers):
    resolve_state.update(phase="Linking seasons", total=len(names), done=0)
    nodes, frontier = {}, {covers[n]["id"] for n in names}
    for _ in range(20):   # one batched call per step along the prequel/sequel links
        missing = [i for i in frontier if i not in nodes]
        if not missing:
            break
        frontier = set()
        for i, m in gql_batch(lambda i: f"Media(id:{i}){{{SEASON_FIELDS}}}", missing, 25).items():
            if m:
                nodes[i] = m
                frontier.update(e["node"]["id"] for e in m["relations"]["edges"]
                                if e["relationType"] in ("PREQUEL", "SEQUEL") and e["node"]["format"] in SEASON_FORMATS + BRIDGE_FORMATS
                                and same_series(m["title"], e["node"].get("title") or {}))
    built = {}
    for n in names:
        try:
            built[n] = {"at": time.time(), "v": SEASONS_V, "seasons": build_seasons(covers[n]["id"], nodes),
                        "rel": related_ids(covers[n]["id"], nodes)}
        except Exception as e:
            print("seasons failed:", n, e)
        resolve_state["done"] += 1
        if len(built) >= 50 or n == names[-1]:
            with seasons_lock:
                try:
                    with open(SEASONS_DB) as f:
                        db = json.load(f)
                except FileNotFoundError:
                    db = {}
                db.update(built)
                with open(SEASONS_DB, "w") as f:
                    json.dump(db, f, indent=1)
            built = {}


def resolve_info(ids):
    resolve_state.update(phase="Getting details", total=len(ids), done=0)
    for k in range(0, len(ids), 40):
        chunk = ids[k:k + 40]
        got = gql_batch(lambda i: f"Media(id:{i}){{{INFO_FIELDS}}}", chunk, 20)
        with info_lock:
            db = load_info()
            for i, m in got.items():
                if m:
                    db[str(i)] = keep_mal({"at": time.time(), **info_from(m)}, db.get(str(i)) or {})
            save_info(db)
        resolve_state["done"] += len(chunk)
        for i in chunk:
            want_rating(i)


def resolve_all():
    items = read_items()
    kinds = {it["name"]: "MOVIE" if it["progress"].strip().lower() == "movie" else None for it in items}
    with cover_lock:
        covers = load_covers()
    todo = [n for n in kinds if needs_match(covers.get(n))]
    if todo:
        resolve_matches(todo, kinds, covers)
    matched = [n for n in kinds if (covers.get(n) or {}).get("file") and covers[n].get("id")]
    with seasons_lock:
        try:
            with open(SEASONS_DB) as f:
                sdb = json.load(f)
        except FileNotFoundError:
            sdb = {}
    stale = [n for n in matched if not seasons_fresh(sdb.get(n))]
    if stale:
        resolve_seasons(stale, covers)
    with info_lock:
        idb = load_info()
    ids = list(dict.fromkeys(covers[n]["id"] for n in matched if info_stale(idb.get(str(covers[n]["id"])))))
    if ids:
        resolve_info(ids)


def resolve_loop():
    resolve_state["wake"].set()
    while True:
        resolve_state["wake"].wait(3600)   # after list changes, and hourly for airing shows
        time.sleep(4)   # let a burst of edits settle
        resolve_state["wake"].clear()
        resolve_state.update(running=True, error="")
        try:
            resolve_all()
        except Exception as e:
            resolve_state["error"] = str(e)
            print("resolve failed:", e)
        finally:
            resolve_state.update(running=False, phase="", done=0, total=0)


def known():
    """Everything already saved about the list's shows, so the page can fill in at once."""
    with cover_lock:
        covers = load_covers()
    with seasons_lock:
        try:
            with open(SEASONS_DB) as f:
                sdb = json.load(f)
        except FileNotFoundError:
            sdb = {}
    with info_lock:
        idb = load_info()
    out = {"seasons": {}, "rel": {}, "info": {}, "match": {}, "resolve": {k: v for k, v in resolve_state.items() if k != "wake"}}
    for it in read_items():
        n, c = it["name"], covers.get(it["name"])
        if c is None:
            continue
        out["match"][n] = {"id": c.get("id"), "match": c.get("match"), "fmt": c.get("fmt"), "year": c.get("year"), "conf": c.get("conf"),
                           "manual": bool(c.get("manual") or c.get("search")), "ok": bool(c.get("ok")), "none": not c.get("file")}
        s = sdb.get(n)
        if s and s.get("v") == SEASONS_V:
            out["seasons"][n] = s["seasons"]
            out["rel"][n] = s.get("rel", [])
        i = idb.get(str(c.get("id"))) if c.get("file") else None
        if i and "titles" in i:
            out["info"][n] = i
    return out


def make_backup():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(XLSX, "Anime Watch List.xlsx")
        for path, arc in ((SETTINGS, "settings.json"), (FRIENDS, "friends.json")):
            if os.path.exists(path):
                z.write(path, arc)
        z.writestr("about.txt", f"Animus Obscurus {VERSION} backup, {time.strftime('%Y-%m-%d %H:%M')}\n")
    return buf.getvalue()


def restore_backup(data):
    """Replace the list (and streaming site) from a backup zip, keeping the old list as .bak-before-restore."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        sheet = z.read("Anime Watch List.xlsx")
        settings = z.read("settings.json") if "settings.json" in z.namelist() else None
        friends = z.read("friends.json") if "friends.json" in z.namelist() else None
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=os.path.dirname(XLSX))
    with os.fdopen(fd, "wb") as f:
        f.write(sheet)
    try:
        count = len(read_items(tmp))   # raises if this isn't one of our sheets
    except Exception:
        os.remove(tmp)
        raise ValueError("that file isn't an Animus Obscurus backup")
    if os.path.exists(XLSX):
        shutil.copy2(XLSX, XLSX + ".bak-before-restore")
    os.replace(tmp, XLSX)
    if settings is not None:
        json.loads(settings)
        with open(SETTINGS, "wb") as f:
            f.write(settings)
    if friends is not None:
        json.loads(friends)
        with open(FRIENDS, "wb") as f:
            f.write(friends)
    return count


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_image(self, data, ctype, extra=None):
        """Covers are re-asked for on every page draw; an ETag turns the repeats into tiny 304s (no re-download)."""
        tag = '"%s"' % hashlib.sha1(data).hexdigest()
        if self.headers.get("If-None-Match") == tag:
            self.send_response(304)
            self.send_header("ETag", tag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", tag)
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/items":
            return self.send(200, read_items())
        if self.path == "/api/settings":
            return self.send(200, read_settings())
        if self.path.startswith("/api/discover"):
            q = parse_qs(urlparse(self.path).query)
            season = (q.get("season", [""])[0]).upper()
            try:
                year = int(q.get("year", ["0"])[0])
                if season not in SEASONS or not 1960 <= year <= 2100:
                    raise ValueError("bad season")
                return self.send(200, discover(season, year))
            except ValueError:
                return self.send(400, {"error": "bad season"})
            except Exception as e:
                return self.send(503, {"error": str(e)})
        if self.path.startswith("/api/calendar"):
            q = parse_qs(urlparse(self.path).query)
            try:
                start = int(q.get("start", ["0"])[0]); days = int(q.get("days", ["7"])[0])
                if not 1_000_000_000 < start < 4_000_000_000 or not 1 <= days <= 8:
                    raise ValueError("bad range")
                return self.send(200, calendar(start, days))
            except ValueError:
                return self.send(400, {"error": "bad range"})
            except Exception as e:
                return self.send(503, {"error": str(e)})
        if self.path == "/api/history":
            try:
                with open(HISTORY_DB, encoding="utf-8") as f:
                    return self.send(200, json.load(f))
            except (FileNotFoundError, ValueError):
                return self.send(200, [])
        if self.path == "/api/changelog":
            text = changelog_text()
            return self.send(200, text.encode("utf-8"), "text/plain; charset=utf-8") if text else self.send(404, {"error": "no changelog"})
        if self.path == "/api/about":
            return self.send(200, {"version": VERSION})
        if self.path == "/api/update":
            return self.send(200, update_info())
        if self.path.startswith("/api/search"):
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            try:
                return self.send(200, search_titles(q))
            except Exception as e:
                return self.send(503, {"error": str(e)})
        if self.path == "/api/ids":
            # AniList ids of the shows on the list, so friends' picks can be matched however they are titled.
            # Every season's id counts (read from the saved season chains), so a later season is "on your list" too.
            names = {i["name"] for i in read_items()}
            ids = {e.get("id") or int(e["file"].split(".")[0])
                   for n, e in load_covers().items() if n in names and e.get("file")}
            try:
                with open(SEASONS_DB) as f:
                    for n, ent in json.load(f).items():
                        if n in names:
                            ids.update(p["id"] for x in ent["seasons"] for p in x["parts"])
            except (FileNotFoundError, KeyError, ValueError):
                pass
            return self.send(200, sorted(ids))
        if self.path == "/api/friends":
            db = load_friends()
            return self.send(200, [{"from": who, "at": v["at"], "items": v["items"], "live": bool(v.get("code"))} for who, v in db.items()])
        if self.path == "/api/relay":
            return self.send(200, relay_status())
        if self.path == "/api/recs/export":
            me, doc = export_recs()
            data = json.dumps(doc, indent=1).encode()
            safe = re.sub(r"[^\w-]+", "-", me).strip("-") or "friend"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="animus-recs-{safe}.json"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/backup":
            data = make_backup()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="animus-backup-{time.strftime("%Y-%m-%d")}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/api/known":
            return self.send(200, known())
        if self.path.startswith("/api/cover"):
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            ent = cover_for(name) if name else None
            if not ent or not ent["file"]:
                return self.send(404, {"error": "no cover"})
            try:
                with open(ensure_image(ent), "rb") as f:
                    data = f.read()
            except Exception:
                return self.send(404, {"error": "cover unavailable"})
            return self.send_image(data, "image/jpeg", {"X-Match": ent["match"].encode("ascii", "replace").decode()})
        if self.path.startswith("/api/seasons"):
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            try:
                seasons = seasons_for(name)
            except Exception as e:
                return self.send(503, {"error": str(e)})
            return self.send(200, {"seasons": seasons})
        if self.path.startswith("/api/info"):
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            try:
                info = info_for(name)
            except Exception as e:
                return self.send(503, {"error": str(e)})
            return self.send(200, {"info": info})
        if self.path.startswith("/api/img"):
            url = parse_qs(urlparse(self.path).query).get("url", [""])[0]
            try:
                path, ctype = image_for(url)
            except Exception as e:
                return self.send(404, {"error": str(e)})
            with open(path, "rb") as f:
                data = f.read()
            return self.send_image(data, ctype)
        if self.path == "/api/mascots":
            # Every image in assets/ is a mascot; the page picks one at random per load.
            files = sorted(f for f in (os.listdir(ASSETS) if os.path.isdir(ASSETS) else []) if f.lower().endswith(MASCOT_EXTS))
            if not files and os.path.exists(os.path.join(ASSETS, "mascot.svg")):
                files = ["mascot.svg"]
            return self.send(200, files)
        if self.path.startswith("/assets/"):
            name = os.path.basename(unquote(urlparse(self.path).path[len("/assets/"):]))
            ctype = mimetypes.guess_type(name)[0] or ""
            path = os.path.join(ASSETS, name)
            if not ctype.startswith("image/") or not os.path.isfile(path):
                return self.send(404, {"error": "not found"})
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        self.send(404, {"error": "not found"})

    def do_POST(self):
        # Re-point a title's cover at a different AniList search.
        if self.path == "/api/rename":
            # Titles key the caches, so a renamed show keeps its cover pick and season data.
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                # A match picked by hand (or approved) moves with the name; an automatic one is redone for the new name.
                keep = False
                for lock, path in ((cover_lock, COVER_DB), (seasons_lock, SEASONS_DB)):
                    with lock:
                        try:
                            with open(path) as f:
                                db = json.load(f)
                        except FileNotFoundError:
                            continue
                        if req["from"] in db:
                            ent = db.pop(req["from"])
                            if path == COVER_DB:
                                keep = bool(ent.get("manual") or ent.get("search") or ent.get("ok")) and bool(ent.get("file"))
                            if keep:
                                db[req["to"]] = ent
                            with open(path, "w") as f:
                                json.dump(db, f, indent=1)
                resolve_state["wake"].set()
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        if self.path == "/api/history/import":   # watch dates from an import: {events: [...], replace: [names]}
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                n = import_history(req.get("events") or [], req.get("replace") or [])
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True, "count": n})
        if self.path == "/api/match/ok":   # "Looks right" in Check matches
            try:
                name = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["name"]
                with cover_lock:
                    db = load_covers()
                    if name in db:
                        db[name]["ok"] = True
                        save_covers(db)
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        if self.path in ("/api/relay/share", "/api/relay/follow", "/api/relay/sync"):
            try:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path.endswith("share"):
                    relay_set_sharing(bool(req.get("on")), bool(req.get("reset")))
                    return self.send(200, relay_status())
                if self.path.endswith("follow"):
                    who, count = relay_follow(req.get("code", ""))
                    return self.send(200, {"from": who, "count": count})
                relay_push()
                done, problems = relay_refresh()
                return self.send(200, {"updated": done, "problems": problems})
            except Exception as e:
                return self.send(400, {"error": str(e)})
        if self.path in ("/api/recs/import", "/api/friends/remove"):
            n = int(self.headers.get("Content-Length", 0))
            if n > 5_000_000:
                return self.send(400, {"error": "that file is too big"})
            try:
                doc = json.loads(self.rfile.read(n))
                if self.path == "/api/recs/import":
                    who, count = import_recs(doc)
                    return self.send(200, {"from": who, "count": count})
                with friends_lock:
                    db = load_friends()
                    db.pop(str(doc.get("from", "")), None)
                    with open(FRIENDS, "w", encoding="utf-8") as f:
                        json.dump(db, f, indent=1)
                return self.send(200, {"ok": True})
            except Exception as e:
                return self.send(400, {"error": str(e)})
        if self.path in ("/api/update/check", "/api/update/apply"):
            if self.path.endswith("check"):
                check_update()
                return self.send(200, update_info())
            try:
                ver = apply_update()
            except Exception as e:
                return self.send(400, {"error": str(e)})
            restart_soon()
            return self.send(200, {"ok": True, "version": ver})
        if self.path == "/api/restore":
            n = int(self.headers.get("Content-Length", 0))
            if n > 20_000_000:
                return self.send(400, {"error": "that file is too big to be a backup"})
            try:
                count = restore_backup(self.rfile.read(n))
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True, "count": count})
        if self.path != "/api/cover":
            return self.send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n))
            with cover_lock:
                ent = fetch_cover(req["name"], (req.get("search") or "").strip() or None, req.get("id"))
                db = load_covers()
                db[req["name"]] = ent
                save_covers(db)
            forget_seasons(req["name"])
        except Exception as e:
            return self.send(400, {"error": str(e)})
        if not ent["file"]:
            return self.send(404, {"error": "no AniList match"})
        self.send(200, {"match": ent["match"]})

    def do_PUT(self):
        # The page owns the full list; each edit sends it back whole.
        n = int(self.headers.get("Content-Length", 0))
        if self.path == "/api/settings":
            try:
                req = json.loads(self.rfile.read(n))
                cur = read_settings()
                if "search" in req:
                    search = str(req["search"]).strip()
                    if search and urlparse(search).scheme not in ("http", "https"):
                        raise ValueError("the site must be an http(s) address")
                    cur["search"] = search
                if "me" in req:
                    cur["me"] = str(req["me"]).strip()[:40]
                    relay_state["wake"].set()   # a shared list carries the name
                if "autoupdate" in req:
                    cur["autoupdate"] = bool(req["autoupdate"])
                if "theme" in req:   # {title, h, s} picked from a cover, or null for the default look
                    t = req["theme"]
                    cur["theme"] = None if not t else {"title": str(t["title"])[:200], "h": float(t["h"]) % 360, "s": min(max(float(t["s"]), 0), 100)}
                    if t and str(t.get("art", "")).startswith("/api/"):   # the cover of the season that was picked
                        cur["theme"]["art"] = str(t["art"])[:1000]
                if "look" in req:   # a special look: one of the page's LOOKS ids, or "" for the default
                    cur["look"] = req["look"] if req["look"] in ("paper", "neon", "retro") else ""
                if "lookPick" in req:
                    cur["lookPick"] = bool(req["lookPick"])
                os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
                with open(SETTINGS, "w", encoding="utf-8") as f:
                    json.dump(cur, f, indent=1)
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        if self.path != "/api/items":
            return self.send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(n))
            items, imported = (body["items"], set(body.get("imported") or [])) if isinstance(body, dict) else (body, set())
            items = [{
                "name": str(i["name"]).strip(),
                "progress": str(i.get("progress", "")).strip(),
                "status": i["status"] if i.get("status") in STATUS_LABELS else "not started",
                "notes": str(i.get("notes", "")).strip(),
                "cover": str(i.get("cover", "")).strip(),
                "links": str(i.get("links", "")).strip(),
                "rating": clean_rating(i.get("rating", "")),
                "pinned": bool(i.get("pinned")),
                "rec": bool(i.get("rec")),
                "with": str(i.get("with", "")).strip()[:80],
            } for i in items if str(i.get("name", "")).strip()]
            try:
                old = read_items()
            except Exception:
                old = []
            write_items(items)
            relay_state["wake"].set()
            resolve_state["wake"].set()
            try:
                log_history(old, items, imported)
            except Exception:
                pass   # the log is a bonus; never let it break saving
        except Exception as e:
            return self.send(400, {"error": str(e)})
        self.send(200, {"ok": True, "count": len(items)})


class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # The browser closed a connection while we were answering (a reload, a closed tab). Not an error.
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8765
    ensure_list()
    server = SERVER = Server(("127.0.0.1", port), Handler)
    threading.Thread(target=update_loop, daemon=True).start()
    threading.Thread(target=relay_loop, daemon=True).start()
    threading.Thread(target=resolve_loop, daemon=True).start()
    print(f"Animus Obscurus is running on http://127.0.0.1:{port}  (close this window to stop it)")
    if "--open" in sys.argv:
        webbrowser.open(f"http://127.0.0.1:{port}")
    server.serve_forever()
    if RESTART:
        relaunch()
