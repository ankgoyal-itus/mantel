# Setting up an iPad for Mantel

Start to finish for one iPad: wipe it, set it up as a kiosk, pin it to Mantel,
and check it survives a night. Then do the same for the second one.

Written against iPadOS 18.7.9, which is what both iPads run. Menu names moved
around in earlier releases; if one is not where this says, search Settings.

Allow about 45 minutes, most of it waiting for the erase and the first-run
setup.

## Before you start

- Mantel is running on the Mac and answers at **http://jarvis.local:8000** from
  another device on the house Wi-Fi. (On the Mac: `make install-service`. See
  the README if `jarvis.local` does not resolve.)
- The Mac is set not to sleep. A sleeping Mac is a blank iPad.
- You know the Wi-Fi password.
- You have chosen a **Guided Access passcode** and written it down somewhere
  that is not the iPad. It is not the Mantel parent PIN, and if you lose it the
  only way out is a wipe.
- The iPad's charger, its cable, and the wall mount are to hand.

---

## 1. Wipe it

1. Copy off anything anyone still wants: photos, notes, game saves. This
   erases everything and is not reversible.
2. **Settings → General → Transfer or Reset iPad → Erase All Content and
   Settings**.
3. Enter the passcode or Apple ID password if asked, and confirm. The iPad
   restarts and comes back at "Hello". This takes a few minutes.

## 2. Set it up as new

4. Language, country, then **Set Up Manually** if offered. Do not restore from
   a backup — a fresh iPad is the point.
5. Join the house Wi-Fi.
6. **Skip the Apple ID**, or sign in with the family one if you want the App
   Store later. Mantel itself needs no Apple ID.
7. Skip or turn off: **Siri**, **Screen Time**, **Analytics**, **App
   Analytics**, **Location Services**, **Apple Pay**, **iCloud Keychain**,
   **True Tone** if it is offered here.
8. Set a device passcode if you want one — the kids will not need it once
   Guided Access is running, so a simple one is fine, but do not use "no
   passcode" if the iPad ever leaves the house.

## 3. Display

9. **Settings → Display & Brightness → Auto-Lock → Never.** This is the
   setting that keeps the dashboard on the wall. If Auto-Lock is greyed out,
   turn off Low Power Mode first.
10. Set **brightness to about 40%** with the slider. Bright enough to read
    across the kitchen, dim enough not to glow at night.
11. **Night Shift → Scheduled**, Custom Schedule **21:00 to 06:30**, warmth
    about two-thirds. That matches Mantel's own night window, so the screen
    warms up as the night screen appears.
12. **True Tone off**, if this iPad has it. It shifts colours as the room's
    light changes, which makes the dashboard look wrong in photographs and
    inconsistent between the two iPads.

## 4. Guided Access

Guided Access is what stops a swipe, a Home press or a curious four-year-old
leaving Mantel.

13. **Settings → Accessibility → Guided Access → on.**
14. **Passcode Settings → Set Guided Access Passcode.** Use the one you wrote
    down. Leave Face ID / Touch ID off for this: a passcode is the reliable
    way out.
15. **Accessibility Shortcut → on.** This is what makes the triple-click work.
16. **Display Auto-Lock → Never**, inside the Guided Access settings, where
    that option is offered. It is a separate setting from step 9 and both
    matter.

## 5. Quiet it down

17. **Settings → Notifications**: go through the list and allow none. Nothing
    should ever appear over the dashboard.
18. **Settings → Focus → Do Not Disturb → Schedule**, **21:00 to 06:30**.
    Add a schedule, set the times, and leave "Smart Activation" off.
19. **Settings → Wi-Fi**: the house network joined, and **Auto-Join on** for
    it. Tap the ⓘ next to the network to check.
20. **Settings → General → Software Update → Automatic Updates**: turn
    **Download iOS Updates** and **Install iOS Updates** off. An update that
    reboots the iPad overnight takes the dashboard down with it, and these
    iPads are old enough that an update may never come anyway.
21. **Settings → Sounds**: mute, or turn the volume right down.

## 6. Add Mantel to the home screen

22. Open **Safari** and go to **http://jarvis.local:8000**. The dashboard
    should appear. If it does not, see the troubleshooting table below before
    going on.
23. Tap the **Share** button (the square with the arrow), then **Add to Home
    Screen**.
24. Name it **Mantel** and tap Add.
25. **Close Safari completely**: double-click the Home button (or swipe up and
    pause) and swipe Safari away.
26. Open **Mantel from the home screen**. It must be opened this way — that is
    what makes it run full-screen, with no address bar and no Safari buttons.

## 7. Start Guided Access

27. With Mantel open and showing the dashboard, **triple-click the Home
    button** — or the top button on an iPad without a Home button.
28. Tap **Guided Access**, then **Options** in the bottom-left corner, and
    set:

    | Option | Set to | Why |
    | --- | --- | --- |
    | Sleep/Wake Button | **off** | the top button cannot blank the screen |
    | Volume Buttons | **off** | no accidental volume overlay |
    | Touch | **on** | Mantel needs taps |
    | Time Limit | **off** | it must never end on its own |

29. Tap **Start** (top right). The screen flashes "Guided Access Started".

## 8. Mount it and check it

30. Mount the iPad and plug it in. It stays plugged in permanently — Auto-Lock
    Never will flatten a battery in a few hours.
31. **Triple-tap the top-left corner** of the screen (three quick taps within
    the corner) to open the diagnostics screen, and check:

    - **standalone** is `true` — it was opened from the home screen, not
      Safari. If it says `false`, go back to step 25.
    - **/api/health** shows a block of JSON with `"status": "ok"` and content
      files reading `ok`. If it says `unreachable`, the iPad cannot see the
      Mac.
    - **viewport** reads something like `1024 x 768`. Note it down; it is what
      the layout is designed against.

32. To leave diagnostics: double-click the Home button (Guided Access will ask
    for its passcode first), swipe Mantel away, and open it again from the home
    screen. There is no back button on that screen yet.
33. Restart Guided Access after that (step 27).
34. **Leave it overnight.** In the morning, before anyone touches it, check
    that the screen is **awake** and showing the **night screen** — dim, just
    the clock — until 06:30, and the dashboard after. If it is black, the iPad
    slept (step 9 or 16) or the Mac did.

## 9. The second iPad

Repeat every step. Both iPads run the same app from the same Mac; nothing is
per-device, and they do not need to know about each other.

---

## When something is wrong

| What you see | What it usually is | What to do |
| --- | --- | --- |
| **White or blank screen** after opening Mantel | The build is missing or half-written, so there is nothing for Safari to run | On the Mac: `make build`, then reload the iPad. `make smoke` checks that every file `index.html` names is really in the build. Confirm on `/diag` that `/api/health` is reachable — a white screen with a working API is always the build |
| **"updated" chip is amber** in the bottom corner | The iPad has not had a fresh answer from the API for a while: the Mac is asleep, or the Wi-Fi dropped | Wake the Mac and check it is not sleeping (README, "The Mac must not sleep"). Then check the iPad is on the house Wi-Fi, not a guest network. The dashboard keeps showing the last good content meanwhile, so nothing is lost |
| **Wrong time, or yesterday's day** | The iPad's own clock or timezone. The dashboard's date comes from the Mac; the clock is the iPad's | **Settings → General → Date & Time → Set Automatically on**, timezone **America/Los_Angeles** (Cupertino or Los Angeles in the picker) |
| **No photos in the frame** | Today: the photo frame is still a placeholder and has no photos to show — a clock on a dark screen is correct. Later: the upload token or the Shortcut that sends the photos | Once the frame is built: check `MANTEL_UPLOAD_TOKEN` in `.env` on the Mac and the photo Shortcut on the phone that uses it |
| **Can't get out of Mantel** | Guided Access is doing its job | Triple-click the Home (or top) button and enter the Guided Access passcode. If the passcode is lost, the only way out is to erase the iPad and start at step 1 |
| **Stuck on the diagnostics screen** | It has no way back yet, and a reload keeps you there | Double-click Home, swipe Mantel away, open it from the home screen again (step 32) |
| **Dashboard is there but everything is empty** | The API is up but its content is not: a YAML file in `home/content/` is broken | `/diag` shows which one — look for `"error: ..."` next to a file name under `content`. The Mac's log has the line number: `tail ~/Library/Logs/mantel/api.log` |
