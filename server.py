#!/usr/bin/env python3
"""Local anime list: serves index.html and keeps the Excel sheet in sync. Stdlib only."""
import hashlib, io, json, mimetypes, os, re, shutil, sys, tempfile, threading, time, urllib.error, urllib.request, webbrowser, zipfile
from urllib.parse import parse_qs, unquote, urlparse
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

VERSION = "1.3.2"
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
QUERY = """query($s:String){Media(search:$s,type:ANIME){id title{romaji english} coverImage{large}}}"""
ID_QUERY = """query($id:Int){Media(id:$id,type:ANIME){id title{romaji english} coverImage{large}}}"""
SEARCH_QUERY = """query($s:String){Page(perPage:8){media(search:$s,type:ANIME,sort:SEARCH_MATCH){
  id format seasonYear title{romaji english} coverImage{medium}}}}"""
SEASON_QUERY = """query($id:Int){Media(id:$id){id format episodes title{romaji english}
  coverImage{large} nextAiringEpisode{episode airingAt} relations{edges{relationType node{id format}}}}}"""
SEASONS_DB = os.path.join(ROOT, "data", "seasons.json")
AIRING_TTL = 3 * 3600     # airing shows gain episodes weekly
SEASONS_TTL = 7 * 24 * 3600
TV = ("TV", "TV_SHORT")
rate_lock = threading.Lock()
next_slot = [0.0]


def gql(query, variables, key="Media"):
    """One AniList call, spaced out to stay under their rate limit (retrying on 429)."""
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://graphql.anilist.co", body,
                                 {"Content-Type": "application/json", "User-Agent": "anime-list"})
    for attempt in range(3):
        with rate_lock:
            now = time.time()
            wait = next_slot[0] - now
            next_slot[0] = max(now, next_slot[0]) + 0.7
        if wait > 0:
            time.sleep(wait)
        try:
            return json.load(urllib.request.urlopen(req, timeout=15))["data"][key]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            time.sleep(float(e.headers.get("Retry-After") or 5))


def load_covers():
    try:
        with open(COVER_DB) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def search_terms(name):
    """The title as written, then looser versions (sheet names carry extras like ': Netflix')."""
    loose = re.sub(r"\s*[:\-–]\s*(netflix|season\s*\d+|s\d+).*$", "", name, flags=re.I)
    return list(dict.fromkeys([name, loose, name.split(":")[0].strip()]))


def fetch_cover(name, search=None, media_id=None):
    """Look the title up on AniList and cache the image. Returns the cache entry."""
    os.makedirs(COVERS, exist_ok=True)
    if media_id:
        return lookup(None, search, media_id)
    for term in ([search] if search else search_terms(name)):
        try:
            return lookup(term, search)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    return {"file": None, "match": "", "search": search or ""}


def lookup(term, search, media_id=None):
    media = gql(ID_QUERY, {"id": media_id}) if media_id else gql(QUERY, {"s": term})
    url = media["coverImage"]["large"]
    fname = f'{media["id"]}.jpg'
    img = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    data = urllib.request.urlopen(img, timeout=15).read()
    with open(os.path.join(COVERS, fname), "wb") as f:
        f.write(data)
    t = media["title"]
    return {"file": fname, "id": media["id"], "match": t.get("english") or t.get("romaji"), "search": search or ""}


def cover_for(name):
    with cover_lock:
        db = load_covers()
        ent = db.get(name)
        if ent is None:
            try:
                ent = fetch_cover(name)
            except Exception as e:
                print("cover lookup failed:", name, e)
                return None  # not cached: transient failures retry next load
            db[name] = ent
            with open(COVER_DB, "w") as f:
                json.dump(db, f, indent=1)
        return ent


INFO_QUERY = """query($id:Int){Media(id:$id){id idMal isAdult seasonYear startDate{year} genres synonyms
  title{romaji english native} tags{name rank isGeneralSpoiler isMediaSpoiler}}}"""
INFO_DB = os.path.join(ROOT, "data", "info.json")
INFO_TTL = 30 * 24 * 3600
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


def jikan_rating(mal_id):
    """MyAnimeList's rating text for a show ('R+ - Mild Nudity'), None if MAL has none.
    Raises JikanDown on any failure and then makes no more calls for JIKAN_PAUSE."""
    with jikan_lock:
        if time.time() < jikan_pause_until[0]:
            raise JikanDown("paused")
        time.sleep(JIKAN_GAP)
        req = urllib.request.Request(f"https://api.jikan.moe/v4/anime/{mal_id}", headers={"User-Agent": "anime-list"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=6))["data"].get("rating")
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


def fetch_rating(media_id):
    """Ask MAL for one title's rating and save it. Failures are remembered so we don't retry soon."""
    with info_lock:
        ent = load_info().get(str(media_id))
    if not ent or ent.get("rated"):
        return
    try:
        text = jikan_rating(ent["mal"]) if ent.get("mal") else None
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
        if (not ent or ent.get("rated") or media_id in rating_queue
                or time.time() - ent.get("rating_try", 0) < RATING_RETRY
                or time.time() < jikan_pause_until[0]):
            return
        rating_queue.append(media_id)
        if rating_worker[0] is None:
            rating_worker[0] = threading.Thread(target=drain_ratings, daemon=True)
            rating_worker[0].start()


def build_info(media_id):
    """Everything AniList knows; the age rating comes later from MAL, in the background."""
    m = gql(INFO_QUERY, {"id": media_id})
    names = list(m["title"].values()) + (m["synonyms"] or [])
    tags = sorted((t for t in m["tags"] if t["rank"] >= 60 and not t["isGeneralSpoiler"] and not t["isMediaSpoiler"]),
                  key=lambda t: -t["rank"])
    code, text = rating_code(None, m["isAdult"])
    return {"year": m["seasonYear"] or (m["startDate"] or {}).get("year"),
            "rating": code, "ratingText": text, "mal": m.get("idMal"), "adult": m["isAdult"],
            "rated": not m.get("idMal"),   # nothing to ask MAL about without an id
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
    if not ent or time.time() - ent["at"] > INFO_TTL:
        try:
            fresh = {"at": time.time(), **build_info(media_id)}
        except Exception:
            if not ent:
                raise
            fresh = None   # AniList is down: show what we have
        if fresh:
            with info_lock:
                db = load_info()
                old = db.get(str(media_id)) or {}
                if old.get("rated") and fresh.get("mal") == old.get("mal"):
                    fresh.update({k: old[k] for k in ("rating", "ratingText", "rated")})
                db[str(media_id)] = ent = fresh
                save_info(db)
    want_rating(media_id)
    return ent


def episode_count(node):
    """Episodes out so far: for an airing show that's one before the next to air."""
    nxt = node.get("nextAiringEpisode")
    if nxt:
        return nxt["episode"] - 1
    return node["episodes"] or None


def build_seasons(media_id):
    """Walk AniList's prequel/sequel links to list a series' TV seasons in order."""
    nodes = {}

    def node(i):
        if i not in nodes:
            nodes[i] = gql(SEASON_QUERY, {"id": i})
        return nodes[i]

    def related(n, kind):
        return [e["node"]["id"] for e in n["relations"]["edges"]
                if e["relationType"] == kind and e["node"]["format"] in TV]

    cur = media_id
    for _ in range(12):
        pre = related(node(cur), "PREQUEL")
        if not pre:
            break
        cur = pre[0]
    chain, seen = [cur], {cur}
    for _ in range(15):
        nxt = [i for i in related(node(chain[-1]), "SEQUEL") if i not in seen]
        if not nxt:
            break
        chain.append(nxt[0])
        seen.add(nxt[0])
    # AniList files each cour as its own entry; fold "Part 2" / "Cour 2" into the season before it.
    groups = []
    for i in chain:
        m = nodes[i]
        title = m["title"].get("english") or m["title"].get("romaji")
        if groups and re.search(r"\b(part|cour)\s*[2-9]\b|second half|2nd cour", title, re.I):
            groups[-1]["parts"].append({"id": i, "episodes": episode_count(m)})
        else:
            groups.append({"title": title, "parts": [{"id": i, "episodes": episode_count(m)}]})
    out = []
    for n, g in enumerate(groups, 1):
        known = [p["episodes"] for p in g["parts"] if p["episodes"] is not None]  # unreleased parts count as 0
        nxt = [nodes[p["id"]]["nextAiringEpisode"] for p in g["parts"] if nodes[p["id"]].get("nextAiringEpisode")]
        out.append({"n": n, "title": g["title"], "parts": g["parts"],
                    "next": {"episode": nxt[0]["episode"], "at": nxt[0]["airingAt"]} if nxt else None,
                    "cover": nodes[g["parts"][0]["id"]]["coverImage"]["large"],
                    "episodes": sum(known) if known else None,
                    "airing": any(nodes[p["id"]].get("nextAiringEpisode") for p in g["parts"])})
    return out


def seasons_for(name):
    with seasons_lock:
        try:
            with open(SEASONS_DB) as f:
                db = json.load(f)
        except FileNotFoundError:
            db = {}
        ent = db.get(name)
        if ent and not all("cover" in x for x in ent["seasons"]):
            ent = None  # cached before covers were stored
        if ent and any(x.get("airing") and "next" not in x for x in ent["seasons"]):
            ent = None  # airing shows cached before air dates were stored
        airing = ent and any(x.get("airing", True) for x in ent["seasons"])
        next_aired = ent and any(x.get("next") and x["next"]["at"] < time.time() for x in ent["seasons"])
        if ent and not next_aired and time.time() - ent["at"] < (AIRING_TTL if airing else SEASONS_TTL):
            return ent["seasons"]
        cover = cover_for(name)
        if not cover or not cover["file"]:
            return None
        media_id = cover.get("id") or int(cover["file"].split(".")[0])
        seasons = build_seasons(media_id)
        db[name] = {"at": time.time(), "seasons": seasons}
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
  studios(isMain:true){nodes{name}} coverImage{extraLarge} title{romaji english}
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
        if ent and time.time() - ent["at"] < ttl:
            return ent
        shows = []
        try:
            for page in range(1, 5):
                data = gql(DISCOVER_QUERY, {"season": season, "year": year, "page": page}, "Page")
                for m in data["media"]:
                    t = m["title"]
                    nxt = m.get("nextAiringEpisode")
                    shows.append({"id": m["id"], "title": t.get("english") or t["romaji"], "format": m["format"],
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


def import_recs(doc):
    """Keep a friend's exported list (replacing their earlier one). Everything in it is treated as untrusted text."""
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
        db[who] = {"at": time.time(), "items": items}
        with open(FRIENDS, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=1)
    return who, len(items)


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
            names = {i["name"] for i in read_items()}
            return self.send(200, {n: (e.get("id") or int(e["file"].split(".")[0]))
                                   for n, e in load_covers().items() if n in names and e.get("file")})
        if self.path == "/api/friends":
            db = load_friends()
            return self.send(200, [{"from": who, "at": v["at"], "items": v["items"]} for who, v in db.items()])
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
        if self.path.startswith("/api/cover"):
            name = parse_qs(urlparse(self.path).query).get("name", [""])[0]
            ent = cover_for(name) if name else None
            if not ent or not ent["file"]:
                return self.send(404, {"error": "no cover"})
            with open(os.path.join(COVERS, ent["file"]), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Match", ent["match"].encode("ascii", "replace").decode())
            self.end_headers()
            self.wfile.write(data)
            return
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
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
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
                for lock, path in ((cover_lock, COVER_DB), (seasons_lock, SEASONS_DB)):
                    with lock:
                        try:
                            with open(path) as f:
                                db = json.load(f)
                        except FileNotFoundError:
                            continue
                        if req["from"] in db:
                            db[req["to"]] = db.pop(req["from"])
                            with open(path, "w") as f:
                                json.dump(db, f, indent=1)
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
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
                with open(COVER_DB, "w") as f:
                    json.dump(db, f, indent=1)
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
                if "autoupdate" in req:
                    cur["autoupdate"] = bool(req["autoupdate"])
                if "theme" in req:   # {title, h, s} picked from a cover, or null for the default look
                    t = req["theme"]
                    cur["theme"] = None if not t else {"title": str(t["title"])[:200], "h": float(t["h"]) % 360, "s": min(max(float(t["s"]), 0), 100)}
                os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
                with open(SETTINGS, "w", encoding="utf-8") as f:
                    json.dump(cur, f, indent=1)
            except Exception as e:
                return self.send(400, {"error": str(e)})
            return self.send(200, {"ok": True})
        if self.path != "/api/items":
            return self.send(404, {"error": "not found"})
        try:
            items = json.loads(self.rfile.read(n))
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
            write_items(items)
        except Exception as e:
            return self.send(400, {"error": str(e)})
        self.send(200, {"ok": True, "count": len(items)})


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8765
    ensure_list()
    server = SERVER = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=update_loop, daemon=True).start()
    print(f"Animus Obscurus is running on http://127.0.0.1:{port}  (close this window to stop it)")
    if "--open" in sys.argv:
        webbrowser.open(f"http://127.0.0.1:{port}")
    server.serve_forever()
    if RESTART:
        relaunch()
