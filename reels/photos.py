"""Bring photos and videos from Google Photos into a reel, read only, through the Photos Picker API.

    reels/photos --login                      once: sign in, read only (prints a link)
    reels/photos <nnnn-slug> [--new] [--max N] [--plan] [--force]
    reels/photos <nnnn-slug> <share link> [--new]   what a Google Photos share link shares; no sign-in

Prints a Google Photos link. Open it (phone or laptop), tap the shots you want and press Done; the
originals download into <content root>/<nnnn-slug>/drive/ (--new makes it for a reel that starts here), beside what reels/pull brought, so
reels/sync sees them (a silent video or a still is b-roll; HDR is tone-mapped there). Each item is
listed in drive/photos.json.

Read only: the permission is photospicker.mediaitems.readonly. It reaches only the items picked in
that session, and it cannot see the rest of the library, change anything or delete anything.
It has its own sign-in (reels/photos --login, once), separate from gws's, through the same Google
Cloud app gws uses; the Photos Picker API must be on in that project.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
API = "https://photospicker.googleapis.com/v1"


def fail(message: str) -> "NoReturn":  # noqa: F821
    print(f"reels/photos: {message}", file=sys.stderr)
    sys.exit(1)


def content_root() -> Path:
    root = os.environ.get("CONTENT_ROOT", "")
    for source in (REPO / ".env", REPO / "PATH.md"):
        if root and root != "/path/to/content":
            break
        if source.exists():
            for line in source.read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTENT_ROOT="):
                    root = line.split("=", 1)[1].strip().strip('"\'')
    if not root or root == "/path/to/content":
        fail("no content root: set CONTENT_ROOT in .env or PATH.md (see edit/README.md)")
    return Path(root)


CLIENT = Path(os.environ.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", Path.home() / ".config/gws")) / "client_secret.json"
STORE = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "reels"
TOKEN = STORE / "photos-token.json"      # this command's own read-only sign-in; gws's is untouched
PENDING = STORE / ".photos-login.json"
REDIRECT = "http://localhost:8723/"


def client() -> dict:
    """The OAuth client gws uses (your own Google Cloud app), from its client_secret.json."""
    try:
        data = json.loads(CLIENT.read_text())
    except (OSError, json.JSONDecodeError):
        fail(f"no OAuth client at {CLIENT}; set up gws first (gws auth setup)")
    return data.get("installed") or data.get("web") or fail(f"{CLIENT} is not an OAuth client file")


def save_private(path: Path, data: dict) -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    STORE.chmod(0o700)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(json.dumps(data))


def token_request(fields: dict) -> dict:
    app = client()
    body = urllib.parse.urlencode({"client_id": app["client_id"], "client_secret": app["client_secret"], **fields}).encode()
    try:
        with urllib.request.urlopen("https://oauth2.googleapis.com/token", body, timeout=30) as reply:
            return json.load(reply)
    except urllib.error.HTTPError as error:
        reason = json.loads(error.read() or b"{}").get("error", error.code)
        fail(f"Google refused the sign-in ({reason}); run reels/photos --login again")


def login(pasted: str | None) -> None:
    """Sign in with only the read-only Photos permission. Two steps, for a headless server:
    --login prints a link; open it anywhere, allow, and paste the localhost address it lands on
    (the page itself will not load: that is expected) into --login '<address>'."""
    if not pasted:
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        save_private(PENDING, {"verifier": verifier, "state": state})
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        link = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": client()["client_id"], "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE,
            "access_type": "offline", "prompt": "consent", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256"})
        print("1. Open this link, sign in and allow read-only access to the photos you pick:\n")
        print(f"  {link}\n")
        print("2. The browser then fails to load a localhost page. That is expected: copy that whole address and run")
        print("     reels/photos --login '<the address>'")
        return
    try:
        pending = json.loads(PENDING.read_text())
    except (OSError, json.JSONDecodeError):
        fail("no sign-in in progress; run reels/photos --login first")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
    if query.get("error"):
        fail(f"sign-in was not allowed ({query['error'][0]})")
    if query.get("state", [""])[0] != pending["state"]:
        fail("that address is from another sign-in; run reels/photos --login again")
    token = token_request({"code": query.get("code", [""])[0], "code_verifier": pending["verifier"],
                           "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    if SCOPE not in token.get("scope", "").split() or "refresh_token" not in token:
        fail("Google did not grant the read-only Photos permission; run reels/photos --login again")
    save_private(TOKEN, {"refresh_token": token["refresh_token"], "scope": token["scope"]})
    PENDING.unlink(missing_ok=True)
    print(f"signed in, read only (permission: {SCOPE}); saved to {TOKEN}")


def access_token() -> str:
    """A short-lived access token from this command's own saved sign-in, kept in memory."""
    try:
        saved = json.loads(TOKEN.read_text())
    except (OSError, json.JSONDecodeError):
        fail("not signed in to Google Photos yet; run reels/photos --login")
    token = token_request({"refresh_token": saved["refresh_token"], "grant_type": "refresh_token"})
    if SCOPE not in token.get("scope", "").split():
        fail("the saved sign-in lacks the read-only Photos permission; run reels/photos --login")
    return token["access_token"]


def call(token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as reply:
            text = reply.read()
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        if error.code == 403 and ("SERVICE_DISABLED" in detail or "has not been used" in detail):
            fail("the Photos Picker API is off in gws's Google Cloud project; turn it on at "
                 "https://console.cloud.google.com/apis/library/photospicker.googleapis.com and try again")
        fail(f"{method} {path}: {error.code} {detail[:300]}")


def seconds(duration: str, default: float) -> float:
    match = re.fullmatch(r"([0-9.]+)s", duration or "")
    return float(match.group(1)) if match else default


def safe_name(name: str, taken: set[str]) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "photo"
    stem, dot, ext = name.rpartition(".")
    stem, ext = (stem, "." + ext) if dot else (name, "")
    candidate, n = name, 2
    while candidate in taken:
        candidate, n = f"{stem}-{n}{ext}", n + 1
    taken.add(candidate)
    return candidate


def download(token: str, url: str, dest: Path) -> int:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    part = dest.with_name("." + dest.name + ".part")
    with urllib.request.urlopen(request, timeout=600) as reply, open(part, "wb") as out:
        while chunk := reply.read(1 << 20):
            out.write(chunk)
    part.replace(dest)
    return dest.stat().st_size


def from_share(link: str, dest: Path, force: bool) -> None:
    """Download every item behind a Google Photos share link (photos.app.goo.gl/..., or
    photos.google.com/share/...). A share link is public, so no sign-in is needed."""
    agent = {"User-Agent": "Mozilla/5.0"}
    with urllib.request.urlopen(urllib.request.Request(link, headers=agent), timeout=60) as reply:
        page = reply.read().decode(errors="replace")
    urls = list(dict.fromkeys(re.findall(r"https://lh3\.googleusercontent\.com/pw/[A-Za-z0-9_-]+", page)))
    if not urls:
        fail("no photos or videos found behind that link; is it a Google Photos share link?")
    print(f"{len(urls)} item(s) behind the link")
    listed = dest / "photos.json"
    record = json.loads(listed.read_text()) if listed.exists() else {"items": []}
    known = {entry["id"]: entry for entry in record["items"]}
    taken = {p.name for p in dest.iterdir()}
    for n, url in enumerate(urls, 1):
        key = url.rsplit("/", 1)[1][:40]   # changes on every visit: only a fallback name
        part = dest / f".share-{n}.part"
        kind = "VIDEO"
        try:   # =dv is the video itself; a photo answers it with an error or an image
            reply = urllib.request.urlopen(urllib.request.Request(url + "=dv", headers=agent), timeout=600)
            if not reply.headers.get_content_type().startswith("video/"):
                raise urllib.error.URLError("not a video")
        except (urllib.error.HTTPError, urllib.error.URLError):
            kind = "PHOTO"
            reply = urllib.request.urlopen(urllib.request.Request(url + "=d", headers=agent), timeout=600)
        mime = reply.headers.get_content_type()
        length = int(reply.headers.get("Content-Length") or 0)
        same = [p.name for p in dest.iterdir() if p.is_file() and length and p.stat().st_size == length]
        if same and not force:   # the link's addresses change each visit, so a file is known by its size
            reply.close()
            print(f"  have   {same[0]}")
            known.setdefault(same[0], {"id": same[0], "file": same[0], "type": kind, "mime": mime, "size": length, "share_link": link})
            continue
        with reply, open(part, "wb") as out:
            while chunk := reply.read(1 << 20):
                out.write(chunk)
        # name it by when it was recorded, the way the phone does, when the file says
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time",
                                "-of", "default=nw=1:nk=1", str(part)], capture_output=True, text=True).stdout.strip()
        stamp = re.sub(r"[^0-9]", "", probe)[:14]
        ext = {"video/mp4": ".mp4", "video/quicktime": ".mov", "image/jpeg": ".jpg", "image/png": ".png",
               "image/heic": ".heic", "image/webp": ".webp"}.get(mime, ".bin")
        base = f"PXL_{stamp[:8]}_{stamp[8:]}{ext}" if len(stamp) == 14 else f"photos-{key[:12]}{ext}"
        name = safe_name(base, taken)
        part.replace(dest / name)
        size = (dest / name).stat().st_size
        print(f"  got    {name}  ({size / 1e6:.1f} MB)")
        known = {k: v for k, v in known.items() if v["file"] != name}
        known[name] = {"id": name, "file": name, "type": kind, "mime": mime, "taken": probe or None,
                      "size": size, "share_link": link}
    record["items"] = sorted(known.values(), key=lambda entry: entry["file"])
    listed.write_text(json.dumps(record, indent=1) + "\n")
    print(f"\nlisted in {listed}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="reels/photos", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reel", metavar="nnnn-slug", nargs="?")
    parser.add_argument("link", nargs="?", help="a Google Photos share link: download what it shares instead of opening the picker")
    parser.add_argument("--login", nargs="?", const="", metavar="ADDRESS", help="sign in, read only; then again with the localhost address the browser lands on")
    parser.add_argument("--max", type=int, help="most items that may be picked (default: Google's limit, 2000)")
    parser.add_argument("--plan", action="store_true", help="check the sign-in and show where items would go; open no picker")
    parser.add_argument("--new", action="store_true", help="start a new reel from Google Photos: make <reel>/drive/ if it is not there")
    parser.add_argument("--force", action="store_true", help="download an item again even if drive/ has a file of that name")
    args = parser.parse_args()

    if args.login is not None:
        return login(args.login or None)
    if not args.reel:
        parser.error("name the reel (nnnn-slug), or --login to sign in")
    if not re.fullmatch(r"[0-9]{4}-.+", args.reel):
        fail(f"the reel must be named <nnnn-slug>, for example 0003-launch-reel (got {args.reel})")
    reel = content_root() / args.reel
    dest = reel / "drive"
    if not dest.is_dir():
        if not args.new:
            fail(f"no {dest}; start the reel with reels/launch first, or pass --new for a reel that starts from Google Photos")
        if not args.plan:
            dest.mkdir(parents=True)
            print(f"new reel {reel}")
    if args.link:
        if args.plan:
            print(f"would download what {args.link} shares into {dest}/")
            return
        return from_share(args.link, dest, args.force)

    token = access_token()
    print(f"signed in with read-only Google Photos access; items go to {dest}/")
    if args.plan:
        print("plan only: no picker was opened")
        return

    session = call(token, "POST", "/sessions", {"pickingConfig": {"maxItemCount": str(args.max)}} if args.max else {})
    sid = session["id"]
    try:
        print("\nOpen this link, tap the photos and videos for the reel, then press Done:\n")
        print(f"  {session['pickerUri']}\n")
        poll = seconds(session.get("pollingConfig", {}).get("pollInterval", ""), 5.0)
        deadline = time.time() + seconds(session.get("pollingConfig", {}).get("timeoutIn", ""), 1800.0)
        while not session.get("mediaItemsSet"):
            if time.time() > deadline:
                fail("the picker timed out before anything was picked; run reels/photos again")
            time.sleep(max(poll, 2.0))
            session = call(token, "GET", f"/sessions/{sid}")

        items, page = [], None
        while True:
            query = urllib.parse.urlencode({"sessionId": sid, "pageSize": 100, **({"pageToken": page} if page else {})})
            listing = call(token, "GET", f"/mediaItems?{query}")
            items += listing.get("mediaItems", [])
            page = listing.get("nextPageToken")
            if not page:
                break
        print(f"{len(items)} picked")

        listed = dest / "photos.json"
        record = json.loads(listed.read_text()) if listed.exists() else {"items": []}
        known = {entry["id"]: entry for entry in record["items"]}
        taken = {p.name for p in dest.iterdir()} - {entry["file"] for entry in known.values()}
        for item in items:
            media = item.get("mediaFile", {})
            video = item.get("type") == "VIDEO"
            name = known[item["id"]]["file"] if item["id"] in known else safe_name(media.get("filename", item["id"]), taken)
            target = dest / name
            if target.exists() and not args.force:
                print(f"  have   {name}")
                continue
            # =d: the original photo (with its metadata, without location); =dv: the video itself
            try:
                size = download(token, media["baseUrl"] + ("=dv" if video else "=d"), target)
            except urllib.error.HTTPError as error:
                print(f"  failed {name}: {error.code} (a video still processing in Google Photos? try again later)", file=sys.stderr)
                continue
            print(f"  got    {name}  ({size / 1e6:.1f} MB)")
            known[item["id"]] = {"id": item["id"], "file": name, "type": item.get("type"), "mime": media.get("mimeType"),
                                 "taken": item.get("createTime"), "size": size,
                                 "width": media.get("mediaFileMetadata", {}).get("width"),
                                 "height": media.get("mediaFileMetadata", {}).get("height")}
        record["items"] = sorted(known.values(), key=lambda entry: entry["file"])
        listed.write_text(json.dumps(record, indent=1) + "\n")
        print(f"\nlisted in {listed}. Next: reels/sync {args.reel} (add --force if raw/ is already made, or --broll for b-roll only)")
    finally:
        try:
            call(token, "DELETE", f"/sessions/{sid}")
        except SystemExit:
            pass


if __name__ == "__main__":
    main()
