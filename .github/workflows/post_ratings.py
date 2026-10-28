import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone

GIST_ID = "585ebcb7bf69836c17f0f11859b8ca27"
FILE = "ratings_export.json"
STATE = "state/seen.json"

WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
TOKEN = os.environ.get("GIST_TOKEN", "")
LOCAL_FILE = os.environ.get("RATINGS_FILE")  # testing: read a local export instead of the Gist
DRY_RUN = os.environ.get("DRY_RUN") == "1"   # testing: print embeds instead of posting

GOLD = 0xEEBA47     # 4.5+ ratings, matches the gold rating badges on the site
NEUTRAL = 0x9B5DFD  # everything else, the site's purple brand accent
SITE_NAME = "Salt & Vi Chips"


def gh_get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ratings-bot",
    })
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")


def load_export():
    if LOCAL_FILE:
        with open(LOCAL_FILE, encoding="utf-8") as f:
            return json.load(f)
    f = json.loads(gh_get(f"https://api.github.com/gists/{GIST_ID}"))["files"][FILE]
    text = f["content"]
    if f.get("truncated"):
        # The Gist API truncates files over 1 MB; the raw URL returns the full file
        text = gh_get(f["raw_url"])
    return json.loads(text)


def song_key(t):
    artists = ", ".join(a.get("name", "") for a in t.get("artists", []))
    return f"{artists}|{t.get('name', '')}".lower()


def current_ratings(export):
    """One entry per song (same title + artist counts once), keeping the highest rating."""
    best = {}
    for bucket in export["ratings"]:
        r = bucket["rating"]
        for t in bucket["tracks"]:
            if not t or not t.get("uri"):
                continue
            k = song_key(t)
            if k not in best or r > best[k][0]:
                best[k] = (r, t)
    return best


def spotify_id(uri):
    return uri.split(":")[-1]


def to_https(url):
    if url.startswith("spotify:image:"):
        return "https://i.scdn.co/image/" + url.split(":")[-1]
    return url


def cover_url(t):
    images = t.get("album", {}).get("images", [])
    large = [i for i in images if i.get("label") == "large"]
    pick = large[0] if large else (images[0] if images else None)
    return to_https(pick["url"]) if pick else None


def stars(r):
    full = int(r)
    half = (r - full) >= 0.5
    empty = 5 - full - (1 if half else 0)
    return "★" * full + ("½" if half else "") + "☆" * empty + f"  {r:g} / 5"


def make_embed(r, t, now_iso):
    album = t.get("album", {})
    artists = ", ".join(a.get("name", "") for a in t.get("artists", [])) or "Unknown artist"
    year = (t.get("release") or {}).get("isoString", "")[:4]
    ms = (t.get("duration") or {}).get("milliseconds")

    parts = []
    if album.get("name"):
        if album.get("uri"):
            parts.append(f"[{album['name']}](https://open.spotify.com/album/{spotify_id(album['uri'])})")
        else:
            parts.append(album["name"])
    if year:
        parts.append(year)
    if ms:
        parts.append(f"{ms // 60000}:{(ms // 1000) % 60:02d}")

    embed = {
        "author": {"name": artists[:256]},
        "title": t.get("name", "Untitled")[:256],
        "url": f"https://open.spotify.com/track/{spotify_id(t['uri'])}",
        "description": " · ".join(parts)[:4096],
        "color": GOLD if r >= 4.5 else NEUTRAL,
        "fields": [{"name": "Rating", "value": stars(r), "inline": True}],
        "footer": {"text": SITE_NAME},
        "timestamp": now_iso,
    }
    cover = cover_url(t)
    if cover:
        embed["thumbnail"] = {"url": cover}
    return embed


def post(embeds):
    body = json.dumps({"embeds": embeds}).encode("utf-8")
    for _ in range(5):
        req = urllib.request.Request(WEBHOOK, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "ratings-bot"})
        try:
            with urllib.request.urlopen(req):
                return
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            retry = json.loads(e.read() or b"{}").get("retry_after", 2)
            time.sleep(float(retry) + 0.5)
    raise RuntimeError("Discord rate limit: gave up after retries")


def save_state(seen):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(seen, f)


def main():
    if not DRY_RUN and not WEBHOOK:
        raise SystemExit("DISCORD_WEBHOOK is not set")
    os.makedirs("state", exist_ok=True)

    export = load_export()
    current = current_ratings(export)
    now_iso = datetime.now(timezone.utc).isoformat()

    if not os.path.exists(STATE):
        # First run: record everything silently so the channel isn't flooded
        seen = {k: r for k, (r, _) in current.items()}
        if not DRY_RUN:
            save_state(seen)
        print(f"First run: recorded {len(current)} songs, nothing posted.")
        return

    with open(STATE, encoding="utf-8") as f:
        seen = json.load(f)

    # New songs, plus songs whose rating changed; highest rated first
    new = [(k, r, t) for k, (r, t) in current.items() if seen.get(k) != r]
    new.sort(key=lambda x: (-x[1], x[2].get("name", "").lower()))

    for i in range(0, len(new), 10):  # Discord accepts up to 10 embeds per message
        chunk = new[i:i + 10]
        embeds = [make_embed(r, t, now_iso) for _, r, t in chunk]
        if DRY_RUN:
            print(json.dumps(embeds, ensure_ascii=False))
        else:
            post(embeds)
            for k, r, _ in chunk:
                seen[k] = r
            save_state(seen)  # save after each batch so a failure doesn't re-post
            time.sleep(2.5)   # stay under the webhook rate limit

    print(f"{'Would post' if DRY_RUN else 'Posted'} {len(new)} ratings")


if __name__ == "__main__":
    main()
