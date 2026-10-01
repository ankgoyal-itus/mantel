# Screens

What the kiosk actually looks like, one picture per state, written here by
the design suite on every `make check`. They are not committed; `make
screenshots` picks the published ones into screenshots/.

    day-morning      07:30, breakfast leading the meals strip
    day-afternoon    15:30, dinner leading
    day-evening      20:30, tomorrow moved up
    night            22:30, the calm screen
    frame            the photo frame with its captions
    pin              the parent PIN pad
    month-family     the calendar as a family reads it
    month-panchang   the same month with the almanac on
    month-panel      a day open in the side panel

Each one again with `-night` on the end, and `night-day.png` the other way
round: the same screen under the other palette. Several of these are screens
the family really does open after ten — the calendar, the list, the frame, a
child's card — and the day dashboard's copy is a check rather than a place
anyone goes, since after the night start the night screen is up instead.
`parent-approvals` has no pair: Shell.tsx hands parent mode the night palette
whatever hour it is opened at.

All at 1024x768, which is what both iPads report. The suite also runs every
check at 2048x1536 (the retina pass, device pixel ratio 2) but leaves no file
there: two copies of every picture would swamp the diff without saying
anything the first does not.

`make smoke` writes day.png, frame.png and day-after-tap.png here too, from
the end-to-end run against a live API. Those three are regenerated from real
data, so they are not committed.
