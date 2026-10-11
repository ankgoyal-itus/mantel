# Photos

> **Since Mantel 0.3.0, uploads go to Memories** (the photo frame app, :8002),
> which owns the photos; Mantel reads the same folder. Everything below works
> the same with Memories' address, `http://albert.local:8002/api/photos`
> (Mantel's old address answers 410 with it). The header can stay
> `X-Mantel-Token` or become `X-Memories-Token`; the token is the same value,
> set in Memories as `MEMORIES_UPLOAD_TOKEN` (see Memories' docs/DEPLOY.md).

How photos get onto the frame. Two ways, and the first one is much less work:

1. **From this Mac** — a script reads the "Mantel" album in Photos and uploads
   it. Set up once, runs itself nightly. This is the one to use.
2. **From the phone** — an iOS Shortcut, for pushing a photo up while you are
   out. Written up at the end; skip it unless you want it.

Either way the photos land in the same place and are treated the same.

---

## 0. The upload token

The token is a shared password: the phone sends it with every upload, and the
API compares it with `MANTEL_UPLOAD_TOKEN` from `.env`. There is nothing to
register and nobody to ask — you invent the value. Until it is set the API
answers uploads with **503** (not configured); with the wrong value, **401**.

**Is one already set?** On the Mac:

    grep MANTEL_UPLOAD_TOKEN <repo>/.env

If that prints `MANTEL_UPLOAD_TOKEN=` followed by a long string, you have one
already — use it, and skip the rest of this section.

**To make one:**

1. Generate a value. In **Terminal**:

        openssl rand -hex 16

   That prints 32 random characters, like `0123456789abcdef0123456789abcdef`.
   Anything unguessable works; this is just a convenient way to get it.

2. Open `<repo>/.env` — in VS Code, or in Terminal with
   `open -e <repo>/.env`.

3. Find the line beginning `MANTEL_UPLOAD_TOKEN=` and put the value straight
   after the `=`, so the whole line reads:

        MANTEL_UPLOAD_TOKEN=0123456789abcdef0123456789abcdef

   **No spaces around the `=`, no quotes, nothing after the value.** A space
   inside the name on the left breaks the line silently and the variable is
   simply never set — that has already happened once in this file.

4. Save it.

5. Restart the API, because `.env` is read once at startup:

        launchctl kickstart -k gui/$(id -u)/com.mantel.api

6. Check it took, from the Mac:

        cd <repo>
        TOKEN=$(grep '^MANTEL_UPLOAD_TOKEN=' .env | cut -d= -f2)
        curl -s -X POST http://albert.local:8002/api/photos \
          -H "X-Mantel-Token: $TOKEN" -F "file=@some-photo.jpg"

   `{"added":["..."]}` means it works. `503` means the restart has not
   happened or the line is malformed.

The file is git-ignored, so the token never leaves the Mac. If you ever change
it, the Shortcut stops working until its header is changed to match — they are
two copies of the same secret.

---

## The Mac way

Everything is already on this Mac through iCloud Photos, so nothing needs to
leave it.

### Once

1. In **Photos**, make an album called **Mantel** and put photos in it. (Another
   name works too: put `MANTEL_ALBUM=Your album` in `.env`.) That
   album is the frame: what is in it goes up, what you remove comes down (at
   the next sync, for new photos — taking one *off* still needs a DELETE, see
   the README).

2. Run the sync once **from Terminal**, by hand:

        cd <repo>
        make photos

   The first run raises a macOS prompt: **"Terminal wants to control Photos"**.
   Click **OK**. Without it the album is skipped and you will see
   `album "Mantel": not permitted` — everything else still works.

   If you ever refuse by accident, it is
   **System Settings → Privacy & Security → Automation → Terminal → Photos**.

3. Install the nightly run:

        make install-photos-service

   That is the `com.mantel.photos` launchd agent: 21:00 every day, logging to
   `~/Library/Logs/mantel/photos.log`. `make uninstall-photos-service` removes
   it.

### After that

Put a photo in the Mantel album whenever you like. It is on the wall by
morning. To push it up now instead:

    make photos

The output is one line:

    album "Mantel": exported 42 | inbox: 0 | uploaded: 42 | new: 3, already had: 39

`new` is what the frame did not have. `already had` is the API recognising
photos by content and skipping them, which is why re-sending the whole album
every night costs nothing but a little time.

### The inbox, when Photos is being difficult

Anything dropped in `inbox/` is uploaded by the same run and then moved to
`inbox/sent/`:

    open <repo>/inbox

Drag photos in from Photos, the Finder, a message, anywhere. This path needs
no permissions at all, so it works even if the Automation prompt was refused
or Photos changes under a macOS update. Non-images in the folder are left
alone.

### When the Mac way does not work

| What you see | What it means | What to do |
| --- | --- | --- |
| `album "Mantel": not permitted` | The Automation prompt was never answered, or was refused | Run `make photos` from Terminal and click OK, or System Settings → Privacy & Security → Automation |
| `album "Mantel": no album` | There is no album with that name | Make one in Photos called exactly `Mantel` |
| `The API is not answering` | The Mantel service is not running | `launchctl print gui/$(id -u)/com.mantel.api \| head`, and the README's service section |
| `No MANTEL_UPLOAD_TOKEN` | `.env` has no token | Section 0 above |
| `new: 0` every night | Everything in the album is already up | Correct. Add new photos to the album |
| `not photos: 3` in the summary | Photos exported sidecar files (`.aae`, describing edits to a photo) or videos alongside the pictures | Nothing to do. They are skipped by name before the API sees them; the frame shows photographs only |
| A photo in the album never appears | It may be a video, a Live Photo exported as `.mov`, or a format Pillow cannot read | Check `home/content/photos/failed/` on the Mac, and the API log for the reason |
| Nothing at 21:00 | The Mac was asleep | launchd runs a missed job when the Mac wakes; check `~/Library/Logs/mantel/photos.log` |

---

## The phone way

An iOS Shortcut named "Send to Mantel". Worth building only if you want to put
a photo up while you are away from the Mac — everything it does, `make photos`
does with less ceremony.

### 1. Make the album

1. In **Photos**, create a new album called **Mantel**.
2. Put some photos in it. Anything in this album is fair game for the frame,
   so it is also how you take a photo *off* the frame later: remove it here,
   and delete it from Mantel with the parent tools when they exist.

### 2. Build the Shortcut

In **Shortcuts → + (new shortcut)**, name it **Send to Mantel**, then add these
actions in order.

3. **Find Photos**
   - Filter: **Album** — **is** — **Mantel**
   - Add filter: **Date Taken** — **is in the last** — **30 days**
   - **Limit** — on — **50** photos
   - Sort by **Date Taken**, **Latest First**

   The 30 days and the limit are there so a daily run stays small and quick.
   Photos already sent are recognised and skipped by the API, so re-sending
   the same ones costs nothing.

4. **Repeat with Each** — with **Photos** (the output of step 3) as the input.

   Inside the repeat:

5. **Get Contents of URL** — this is the action that does the work, and the
   only fiddly one. It shows a single URL field until you open it up:

   1. Put the address in the URL field: `http://albert.local:8002/api/photos`
   2. Tap the **⌄ chevron** at the right of the action — older iOS labels it
      **Show More**. It unfolds to reveal Method, Headers and Request Body.
   3. **Method** → **POST**. Headers and Request Body do nothing until it is
      POST, so do this first.
   4. **Headers** → **Add new header**. Two boxes appear, *Key* and *Text*.
   5. *Key*: `X-Mantel-Token` — typed exactly, with the two hyphens.
   6. *Text*: the token, pasted from `.env` on the Mac. On the Mac:

          grep MANTEL_UPLOAD_TOKEN <repo>/.env

   7. **Request Body** → **Form**.
   8. **Add new field** → choose **File** (not Text). Name it `file`. Tap its
      value box and pick **Repeat Item** from the variable strip above the
      keyboard.

   The field name has to be `file`; that is what the API looks for. The header
   name is not case-sensitive — `x-mantel-token` works — but its spelling and
   hyphens are.

   Three things that actually go wrong here:

   - **iOS rewrites the hyphens.** Smart punctuation can turn `-` into `–`,
     which breaks the header silently. If in doubt, retype the key slowly, or
     turn off Settings → General → Keyboard → Smart Punctuation while you
     build this.
   - **A trailing space on the pasted token.** That is a 401. Tap into the
     value box and check the cursor sits immediately after the last character.
   - **The token put in the body instead of the headers.** It has to be a
     *header*; as a form field the API never sees it, and answers 401.

6. **Get Dictionary Value** — Get **Value** for **added** in **Contents of URL**.
7. **Count** — **Items** in **Dictionary Value**.
8. **Add to Variable** — variable name **Added**.

   Still inside the repeat. Steps 6–8 collect how many photos each request
   actually stored, as opposed to recognised and skipped.

   *(End of the repeat.)*

9. **Calculate Statistics** — **Sum** of **Added**.
10. **Show Result** — `Sent [Statistics] new photos to Mantel`.

### 3. Check the token from the Mac first

If you are not sure whether a failure is the token or the Shortcut, settle it
before touching the phone. On the Mac:

    cd <repo>
    TOKEN=$(grep '^MANTEL_UPLOAD_TOKEN=' .env | cut -d= -f2)
    curl -s -X POST http://albert.local:8002/api/photos \
      -H "X-Mantel-Token: $TOKEN" \
      -F "file=@some-photo.jpg"

`{"added":["..."]}` means the server and the token are fine, and anything still
failing afterwards is in the Shortcut. `{"detail":"bad upload token"}` means
the token itself is wrong. To take that test photo off again:

    curl -s -X DELETE http://albert.local:8002/api/photos/<the id> \
      -H "X-Mantel-Token: $TOKEN"

### 4. Run it

11. Tap the shortcut. The **first run** shows a prompt asking to allow it to
    reach `jarvis.local` on the local network — tap **Allow**. iOS asks once
    per app, and the Shortcut cannot work until you do.
12. The result should read `Sent 5 new photos to Mantel`, or whatever number
    was new. Run it a second time and it should say `Sent 0`: everything is
    already there, which is the de-duplication working.
13. On the iPad, the new photos appear in the frame within `refresh_minutes`
    (five by default). The frame does not restart — they join the rotation.

### 5. Run it by itself, every night

14. **Shortcuts → Automation → + → Time of Day**.
15. **Time of Day** — **21:00**, **Daily**.
16. Action: **Run Shortcut** — **Send to Mantel**.
17. Turn **Run Immediately** on (so it does not ask first) and **Notify When
    Run** off.
18. Optionally add a **Wi-Fi** condition for the home network, so it never
    tries over cellular where `jarvis.local` does not exist. On iOS this is a
    separate automation trigger (**Wi-Fi → joins → your network**); a time
    automation cannot also check Wi-Fi. If you use the time trigger alone, a
    run away from home simply fails and the next one catches up.

---

### When the phone way does not work

| What you see | What it means | What to do |
| --- | --- | --- |
| `401` | The token is wrong or missing | Check `X-Mantel-Token` matches `MANTEL_UPLOAD_TOKEN` in `.env`, exactly, with no stray space |
| `503` | The API has no token configured | Set `MANTEL_UPLOAD_TOKEN` in `.env` on the Mac and restart the service |
| `413` | One photo is over 30 MB | A still photo will not be; this is usually a video or a burst. The frame takes photos only |
| Cannot connect / times out | `jarvis.local` did not resolve, or the Mac is asleep | Try the LAN IP instead. If that works, see the README's network section. If neither does, the Mac is asleep — the README's energy settings |
| Runs, says `Sent 0`, every time | Everything in the album has already been sent | That is correct. Add new photos to the **Mantel** album |
| Nothing new on the iPad after 5 minutes | The kiosk has not re-polled yet, or is not in the frame | Wait one `refresh_minutes`, then triple-tap the top-left corner and check `/api/health` on the diagnostics screen |

## What the API does with them

Each upload is stored exactly as sent, then normalised once: rotated upright
if the phone recorded an orientation, resized so the long edge is 2048 pixels,
re-encoded as JPEG, and stripped of everything except the date it was taken —
no location, no device, no face data reaches the iPad. A file that cannot be
read is moved aside and never shown. See the README for where all of that
lands on disk.
