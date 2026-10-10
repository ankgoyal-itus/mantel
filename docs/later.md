# Later

Ideas parked by any session. Nothing here is built until a prompt asks for it.

Format: one bullet per idea, newest at the bottom, with the date it was parked.

- 2026-09-22 — Task points are parsed and ignored. Scoring, streaks and any
  history behind them wait for SQLite in v2.
- 2026-09-22 — Calendar events merge into a day in `today.merge_agenda()`,
  which is the only place that has to change when they arrive.
- 2026-09-22 — Schedule exceptions match on date and title, so one title
  affects every kid holding it. An optional `kid:` key would narrow that if a
  shared title ever needs splitting.
- 2026-09-22 — An all-day calendar event is placed on its start date only; a
  multi-day all-day event does not yet repeat across the days it spans.
- 2026-09-22 — Calendar events are expanded for today-1 to today+14, so an
  /api/agenda range reaching past that window shows schedule items only.
- 2026-09-22 — A kid column shows three agenda rows and three tasks at
  1024x768, with "+N more" beyond that. A busier day needs either a denser row
  or a second page, not a smaller font.
- 2026-09-22 — Task checkboxes are display-only. Tapping to complete, and a
  parent approving it, arrive with SQLite in v2.
- 2026-09-22 — The Docker image is Cloud-Run-shaped but nothing is set up for
  it, deliberately: the calendar secrets and the photo directory both need an
  answer before Mantel runs anywhere but the house.
- 2026-09-22 — `/diag` has no way back to the dashboard. Today you force-close
  Mantel and reopen it, which docs/ipad-setup.md documents. A corner tap or a
  timeout would do, once parent mode settles how screens are left.
- 2026-09-22 — Keeping a MacBook awake needs `caffeinate` run by hand. A
  second launchd agent would do it at login; the Mac mini makes it moot.
- 2026-09-22 — `make smoke` drives DAY and FRAME only. NIGHT is covered by
  vitest and was checked by hand against the running service; a third leg with
  the clock pinned to 22:00 would fold it into the same script.
- 2026-09-22 — A public iCloud Shared Album could feed the frame without the
  Shortcut, but its web-stream API is unofficial: a 330 redirect to a per-
  account host, then per-asset URLs that expire. It would need its own fetch,
  retry and refresh path, and Apple can change it without notice. Deliberately
  not built; `settings.photos.shared_album_url` does not exist.
- 2026-09-22 — Photos are only removed with DELETE /api/photos/{id} and a
  token. Taking one off the frame from the iPad waits for parent mode.
- 2026-09-23 — is_school_day is one flag for the whole day, so a closure at one
  kid's school reads as a closure for both. Per-kid school days need the day
  model split, which is a bigger change than this prompt wanted.
- 2026-09-23 — The district feed has no "First Day of School" event once term
  has started, so first_day stays unknown until next year's calendar is
  published. last_day is found, which is what the Summer rule needs.
- 2026-09-23 — The panchang engine brings in the Swiss Ephemeris, which is
  AGPL-3.0. Serving Mantel publicly (the Cloud Run idea above) would trigger
  AGPL section 13 and require offering the source to its users. Fine on the
  LAN; decide before anything is deployed.
- 2026-09-23 — MonthScreen fetches a month per visit and holds it for the
  session only. A service worker would keep it across reloads, which needs
  HTTPS, which needs a certificate on the LAN.
- 2026-09-23 — The panchang panel hides yoga and karana behind
  settings.panchang.show_yoga_karana, which nothing in the kiosk can toggle.
  Parent mode is where that switch belongs.
- 2026-09-23 — copy.ts holds the strings the six screens share; the parent
  sections still carry their own inline text. Worth folding in when parent
  mode next changes, rather than churning five files for nothing.
- 2026-09-23 — The design suite renders against a stub API on a static server.
  It never exercises the real endpoints, which is what `make smoke` is for;
  the two should probably share their fixture one day.
- 2026-09-23 — The family jar reads on the family line, not between the two kid
  cards where the v3 prompt asked for it. A strip there costs both cards width
  and they have none: at 456px instead of 480, "Cross Country meet" goes back
  to an ellipsis. One card per screen, or a narrower time column, would free
  the room.
- 2026-09-23 — The rewards shop is three cards across rather than the four the
  prompt asked for, because at four the cards are 150px wide and "Pick
  tomorrow's dinner" loses the word that matters. Shorter reward names would
  allow four.
- 2026-09-23 — A kid pad has no lockout and no delay: it is a latch on a
  sibling, and ten thousand guesses on a touchscreen is its own deterrent. If
  it ever needs to be more than that, the parent pad's lockout is the model.
- 2026-09-23 — The weekly digest is fetched when the Settings tab opens and
  only for the current week. A week picker, and a Sunday-evening nudge, are
  both obvious and neither was asked for.
- 2026-09-23 — Policy rewards (Roblox) are unreachable while enabled:false and
  nothing enforces screen time; approving one would only produce a parent
  to-do. The weekly cap is implemented and tested against that day.
- 2026-09-23 — Points are shown to the kid whose card is open and on the
  dashboard, but there is no history screen: /api/ledger/{kid} is served and
  nothing in the kiosk reads it. "Where did my points go" is a real question a
  child will ask.
- 2026-09-23 — A claim can only be made for today. A chore done on Saturday and
  remembered on Sunday cannot be claimed, which is the right default and the
  wrong answer about twice a month.
- 2026-09-23 — The tomorrow card takes a fifth of the row and a third after
  six, and the two kid cards pay for it: at 374px a card leaves 128px for an
  agenda title, so "Cross Country meet" is an ellipsis again. The end time
  went to buy some of it back. One card per screen, or the rail treatment for
  both, would be the next thing to try.
- 2026-09-23 — A kid card holds two agenda rows and one open routine at
  1024x768. Three agenda rows and three containers want 563px in 434, and the
  design suite now says so out loud. Anything added to the header comes off
  the bottom of both children's cards.
- 2026-09-23 — Saving-for bars: two on the open card in kid mode, one on the
  dashboard card. Two bars apiece is what the dashboard has no room for; one
  fits, and a star that shows nothing where a child walks past does nothing.
  A second bar on the dashboard is the same arithmetic as above.
- 2026-09-23 — The illustration set is inline in
  `components/illustrations/Illustration.tsx` rather than files in
  `public/illustrations`, because an empty state is drawn in the kid's colour
  and an <img> cannot inherit currentColor. Reward glyphs still come from the
  icon set: replacing them would need the shop grid to give up a row.
- 2026-09-23 — "Same as yesterday" never appears for dinner, because the
  four-day repeat rule has already ruled yesterday's dinner out. That is the
  rule working, but it does mean the fast tile is a breakfast and lunch
  feature in practice.
- 2026-09-23 — Birthdays are read from family.yaml and nothing is filled in:
  the dates are the family's to add. Until they are, item 22 is code with no
  data behind it.
- 2026-09-23 — The bedtime check-in has no screen for reading a week back
  except the digest card in parent settings. If it turns out to be used, the
  obvious next thing is a small strip of faces per child on that card.
- 2026-09-23 — A parent's birthday reaches the tomorrow card because it is an
  observance, which also puts it in the month grid and the list. If that turns
  out to be too much, an observance kind of its own would let the screens
  choose.
- 2026-09-23 — The dashboard's routine head is a line now, not a control: the
  budget gives it 40px, under a finger's worth. Switching Morning / After
  school / Evening happens in kid mode, one tap away on the face. If the wall
  turns out to need it, the head would have to grow back to 44 and the card
  lose four pixels of to-dos.
- 2026-09-23 — "+20 today" is summed from today's approved tasks on the Day
  payload, so an award a parent gives does not count towards it. An
  `approved_today` on /api/points/{kid} would make it exact.
- 2026-09-23 — Only DAY is laid out upright. "+N more", "N events" and the
  month all open screens that still say "Turn the iPad sideways" in portrait,
  which is why the events chip is not drawn there at all.
- 2026-09-23 — family.yaml has no name for the family, so the parent rail's
  heading says "Our family". A `name:` there would be one line in the model
  and one in the rail.
- 2026-09-23 — A parent settling a meal from the grid or Approvals sets the
  dish; how it is cooked for the kids (kids_protein) comes from the winning
  pick, or stays veg for a dish no child chose. A protein chip in the parent
  sheet would be the next thing if that turns out to matter.
- 2026-09-23 — Meal analytics, local only. From 24 Sep the week is picked
  from the catalog instead of planned, to learn what the house actually eats.
  Worth building once there are a couple of weeks of picks: per dish, how
  often it was picked, by whom, how often a parent overrode it or went back
  to the plan, and which contested dinners went which way. Everything needed
  is already in meals.yaml history and the ledger; nothing leaves the Mac.
- 2026-10-10 — v4: a Roblox use calls the policy plane instead of making a
  parent to-do. The call site is banks.use_roblox; the request row, its hold
  and the weekly cap are meant to stay exactly as they are.
- 2026-10-10 — Cash-out offers one amount: the whole balance rounded down to
  $5. A child choosing a smaller amount ($20 of $35) is the obvious next ask
  and was not asked for.
- 2026-10-10 — The "+$5 in your piggy bank" toast shows on the screen that
  sees the deposit first; a yes approved while both iPads were asleep is only
  said by the caption and the chips. A per-child "seen" mark in the API would
  let it be said once, the next morning.
- 2026-10-10 — The published pictures in screenshots/ predate the bank (the
  rewards one still says the Roblox rows are off). `make screenshots` redraws
  them.
