import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone

GIST_ID = "585ebcb7bf69836c17f0f11859b8ca27"
FILE = "ratings_export.json"
STATE = "state/seen.json"
UPDATED_STATE = "state/gist_updated_at.txt"

WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
TOKEN = os.environ.get("GIST_TOKEN", "")
LOCAL_FILE = os.environ.get("RATINGS_FILE")  # testing: read a local export instead of the Gist
DRY_RUN = os.environ.get("DRY_RUN") == "1"   # testing: print messages instead of posting

GOLD = 0xEEBA47     # messages with 4.5+ ratings, matches the gold badges on the site
NEUTRAL = 0x9B5DFD  # everything else, the site's purple brand accent
SITE_NAME = "Salt & Vi Chips"
MAX_CHARS = 4000    # keeps each message well under Discord's 6000-character embed limit


def gh_get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ratings-bot",
    })
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8")


def fetch_gist_meta():
    return json.loads(gh_get(f"https://api.github.com/gists/{GIST_ID}"))


def read_export(meta):
    f = meta["files"][FILE]
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


def stars(r):
    full = int(r)
    half = (r - full) >= 0.5
    empty = 5 - full - (1 if half else 0)
    return "★" * full + ("½" if half else "") + "☆" * empty + f"  {r:g} / 5"


def song_line(t):
    artists = ", ".join(a.get("name", "") for a in t.get("artists", [])) or "Unknown artist"
    return f"[{t.get('name', 'Untitled')}](https://open.spotify.com/track/{spotify_id(t['uri'])}) · {artists}"


def build_messages(new):
    """Group new ratings by star level (highest first) and pack them into messages."""
    groups = {}
    for _, r, t in new:
        groups.setdefault(r, []).append(t)

    lines = []  # (text, rating) pairs so each message knows if it has a top rating
    for r in sorted(groups, reverse=True):
        tracks = sorted(groups[r], key=lambda t: t.get("name", "").lower())
        lines.append((f"**{stars(r)}** · {len(tracks)} song{'s' if len(tracks) != 1 else ''}", r))
        for t in tracks:
            lines.append((song_line(t), r))

    messages, cur, size = [], [], 0
    for text, r in lines:
        if cur and size + len(text) + 1 > MAX_CHARS:
            messages.append(cur)
            cur, size = [], 0
        cur.append((text, r))
        size += len(text) + 1
    if cur:
        messages.append(cur)

    now_iso = datetime.now(timezone.utc).isoformat()
    embeds = []
    for i, msg in enumerate(messages):
        top = any(r >= 4.5 for _, r in msg)
        title = f"Ratings update · {len(new)} new" if i == 0 else "Ratings update (continued)"
        embeds.append({
            "title": title,
            "description": "\n".join(text for text, _ in msg)[:4096],
            "color": GOLD if top else NEUTRAL,
            "footer": {"text": SITE_NAME},
            "timestamp": now_iso,
        })
    return embeds


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


def save_updated_at(value):
    with open(UPDATED_STATE, "w", encoding="utf-8") as f:
        f.write(value)


def main():
    if not DRY_RUN and not WEBHOOK:
        raise SystemExit("DISCORD_WEBHOOK is not set")
    os.makedirs("state", exist_ok=True)

    # Cheap check first: the Gist's updated_at only changes when the extension saves
    updated_at = None
    if LOCAL_FILE:
        with open(LOCAL_FILE, encoding="utf-8") as f:
            export = json.load(f)
    else:
        meta = fetch_gist_meta()
        updated_at = meta["updated_at"]
        if os.path.exists(UPDATED_STATE):
            with open(UPDATED_STATE, encoding="utf-8") as f:
                if f.read().strip() == updated_at:
                    print("Gist unchanged since last check, nothing to do.")
                    return
        export = read_export(meta)

    current = current_ratings(export)

    if not os.path.exists(STATE):
        # First run: record everything silently so the channel isn't flooded
        seen = {k: r for k, (r, _) in current.items()}
        if not DRY_RUN:
            save_state(seen)
            if updated_at:
                save_updated_at(updated_at)
        print(f"First run: recorded {len(current)} songs, nothing posted.")
        return

    with open(STATE, encoding="utf-8") as f:
        seen = json.load(f)

    # New songs, plus songs whose rating changed
    new = [(k, r, t) for k, (r, t) in current.items() if seen.get(k) != r]

    embeds = build_messages(new) if new else []
    for i in range(0, len(embeds)):
        if DRY_RUN:
            print(json.dumps([embeds[i]], ensure_ascii=False))
        else:
            post([embeds[i]])
            time.sleep(2.5)  # stay under the webhook rate limit

    if not DRY_RUN:
        for k, r, _ in new:
            seen[k] = r
        save_state(seen)
        if updated_at:
            save_updated_at(updated_at)  # only after everything succeeded, so failures retry
    print(f"{'Would post' if DRY_RUN else 'Posted'} {len(new)} ratings in {len(embeds)} message(s)")


if __name__ == "__main__":
    main()
