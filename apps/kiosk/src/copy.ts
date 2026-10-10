/**
 * Every string the kiosk shows, in one place.
 *
 * House style: sentence case, no colons, no uppercase tracking, times like
 * "4:00 pm", and activities named in full. Empty states say what is true of
 * this family today, not "None".
 */

export const copy = {
  // Only the screens drawn for the wide iPad ask for this.
  shell: {
    turnSideways: 'Turn the iPad sideways',
    waitingForApi: 'Waiting for the API',
    tonight: 'Tonight',
    noForecast: 'No forecast',
    // A tab that threw: the rest of the screen still works.
    partFailed: 'This part did not load. The rest of the screen still works, and the reason is in the browser console on /diag.',
  },
  // The diagnostics page (/diag): for a parent with the iPad in hand.
  diag: {
    title: 'Mantel diagnostics',
    desktopClass: 'iPadOS reports as a Mac in Safari. Add to Home Screen to see the real version.',
    health: '/api/health',
  },
  day: {
    today: 'Today',
    toDo: 'To do',
    allDay: 'All day',
    noSchool: 'No school',
    freeAfternoon: 'Free afternoon',
    noSchoolToday: 'No school today',
    nothingToDo: 'Nothing to do',
    more: (count: number) => `${count} more`,
    // A row of its own at the foot of a list that did not fit, and the way
    // in to the rest of it.
    moreRow: (count: number) => `+${count} more`,
    jar: 'jar',
    // The pill at the end of the family strip. Never a bare number: a 5 on
    // its own at the edge of the screen is a 5 nobody can place.
    familyJar: (points: number) => `Family jar · ${points}`,
    familyNone: 'Nothing for the family today',
    // The last pill, standing in for the ones that did not fit.
    morePills: (count: number) => `+${count}`,
    // What a to-do row says once it has been decided.
    doneFor: (points: number) => `Done · +${points}`,
    notToday: 'Not today',
    // On a meal the children chose differently for, until a parent does.
    // Said to the children, who are the ones reading it on the wall.
    parentsDecide: 'Mom or Dad picks',
    // The "My week" line under a child's headline.
    myWeek: 'My week',
    yoursIs: (weekday: string) => `Yours is ${weekday}`,
    nothingPicked: 'Nothing picked yet',
    // The card that fills the end of the screen when there is room for it.
    comingUp: 'Coming up',
    nothingOn: 'Nothing on',
    // The card's foot: what a parent said yes to today, in points.
    approvedToday: (points: number) => `+${points} today`,
    // The footer's second half, and the headline's: what is still on the
    // table today — open and waiting to-dos.
    stillToEarn: (points: number) => `+${points} still to earn`,
    upTo: (points: number) => `up to +${points} today`,
    // An open to-do's chip: what it is worth.
    worth: (points: number) => `+${points}`,
    // A once-a-week to-do, still to do this week.
    worthWeek: (points: number) => `+${points} · week`,
    // A chip waiting on a parent says so, and what it is worth.
    waitingFor: (points: number) => `Waiting · +${points}`,
    // For five seconds after a claim, the chip says how to take it back.
    tapToUndo: 'Tap again to undo',
    // The one line a child reads before anything else on their card.
    things: (count: number) => (count === 1 ? '1 thing today' : `${count} things today`),
    nextAt: (what: string, when: string) => `${what} at ${when}`,
    nextIn: (what: string, when: string) => `${what} ${when}`,
    // A zero is a poor first impression of a points system; say what to do
    // instead, and let the number appear once there is one.
    startEarning: 'Start earning',
    // On the dashboard the row is read by the parent who has to answer it,
    // so one word is enough; kid mode says who it is waiting for.
    waiting: 'Waiting',
    // The pair that appears in the row itself once a parent has held it down
    // and the PIN is behind them. Said as the answer, not as the action.
    approve: 'Yes',
    decline: 'Not yet',
    // Named, and in the order family.yaml lists them. "Good morning" on its
    // own is a screen talking; with the names on it, it is the house.
    goodMorning: (who: string) => `Good morning, ${who}`,
    goodMorningShort: 'Good morning',
    goodNight: 'Good night',
    // On the day itself, on their own card. Their name, because a card that
    // says "Happy birthday" to nobody in particular is a banner.
    happyBirthday: (name: string) => `Happy birthday, ${name}`,
    // What a bar is counting towards, under the balance.
    savingFor: 'Saving for',
    // How far along, said as the gap rather than the total: a child wants to
    // know how many more, not how many so far.
    toGo: (points: number) => `${points} to go`,
    ready: 'You can ask for this',
    // Said on the pill under the date, when there is no festival to say.
    weekend: 'Weekend',
  },

  kid: {
    // Said as the child would say it, and naming both parents rather than
    // "a grown-up": it is Mom or Dad who taps approve.
    waiting: 'Waiting for Mom or Dad',
    approved: 'Done',
    parentTask: 'Mom or Dad ticks this one',
    undo: 'Undo',
    done: 'Done',
    points: (count: number) => `${count} pts`,
    streak: (days: number) => `${days} day streak`,
    rewards: 'Rewards',
    // The strip under the routines on their own card.
    thisWeekTitle: 'This week',
    thisWeekSaid: (points: number) => `This week, ${points} points`,
    pickMeal: 'Pick a meal',
  },

  // The piggy bank and the Roblox bank: on a kid's own card, and the sheet
  // each one opens. Amounts arrive already said ("$15", "2 h 30 min").
  bank: {
    piggy: 'Piggy bank',
    roblox: 'Roblox bank',
    // The DAY card's caption under the balance: "$15 saved · 2 h Roblox".
    saved: (amount: string) => `${amount} saved`,
    robloxTime: (amount: string) => `${amount} Roblox`,
    // What is left to ask for while something is waiting.
    available: (amount: string) => `${amount} you can use`,
    cashOut: (amount: string) => `Cash out ${amount}`,
    saveMore: (amount: string) => `Save ${amount} more`,
    // Asked in place, on the sheet, before anything is sent.
    askFor: (what: string) => `Ask Mom or Dad for ${what}?`,
    robloxOf: (amount: string) => `${amount} of Roblox`,
    ask: 'Ask',
    notNow: 'Not now',
    asked: 'Asked · waiting for Mom or Dad',
    ofWeek: (used: number, cap: number) => `${used} of ${cap} this week`,
    // The card's toast, for four seconds after a parent says yes.
    inPiggy: (amount: string) => `+${amount} in your piggy bank`,
    inRoblox: (amount: string) => `+${amount} in your Roblox bank`,
    // What a row was, when it says nothing itself.
    cashedOut: 'cashed out',
    used: 'used',
    nothingYet: 'Nothing in here yet.',
    notYet: 'That did not go through.',
    done: 'Done',
  },

  picker: {
    title: "Tomorrow's meals",
    // The week strip, and the list a cell opens.
    week: 'This week',
    slotTitle: (weekday: string, slot: string) => `${weekday} ${slot}`,
    back: 'Week',
    parentsPick: 'Mom or Dad picks',
    locked: 'Locked — too late to change',
    hadThis: (weekday: string) => `we had this ${weekday}`,
    cellLabel: (weekday: string, slot: string, what: string) => `${weekday} ${slot}: ${what}`,
    // Said as a choice about how it is cooked, not as a diet rule.
    way: (protein: string) => (protein === 'veg' ? 'Veg' : `With ${protein}`),
    chose: (name: string) => `${name} it is.`,
    // A treat waits for a parent's OK.
    treatAsked: (name: string) => `${name} — Mom or Dad will say yes or no.`,
    bothChose: (name: string) => `${name} it is — both of you picked it.`,
    notThatOne: 'Not that one, sorry.',
    // The two tiles above the list. Said as offers, not as buttons: a child
    // is being asked whether this will do, not given a command to run.
    again: 'Same as yesterday',
    againWhat: (name: string) => `Again: ${name}`,
    surprise: 'Surprise me',
    nothing: 'Nothing to choose from tomorrow.',
    // How many there are, so the fold at the bottom is plainly a fold and
    // not the end of the list. Said as the thing, not as a count of rows.
    howMany: (count: number, slot: string) => `${count} ${slot}s`,
    // The shelf at the end of lunch or dinner: the other one's dishes.
    alsoGood: (slot: string) => `Also good for ${slot}`,
    // Said once, under the slot chips, instead of on all five faded rows.
    recent: 'Faded ones we had recently',
    // The catalog's cuisine slugs, said the way the family says them. A slug
    // with no entry here is title-cased, so a new one still reads.
    cuisines: {
      indian: 'Indian',
      south_indian: 'South Indian',
      indo_chinese: 'Indo-Chinese',
      mexican: 'Mexican',
      mexican_indian: 'Mexican',
      mediterranean: 'Mediterranean',
      middle_eastern: 'Middle Eastern',
      italian: 'Italian',
      japanese: 'Japanese',
      thai: 'Thai',
      asian: 'Asian',
      western: 'Western',
      fusion: 'Fusion',
    } as Record<string, string>,
    // One tap takes the dish as it comes; the chip is the other way to cook
    // it, and only shows on a day the rule allows it.
    plus: (protein: string) => `+ ${protein}`,
    pick: (names: string[]) =>
      names.length === 0
        ? ''
        : names.length === 1
          ? `${names[0]}'s pick`
          : `${names.join(' and ')} picked this`,
  },

  // A meal eaten out: Lunch out and Dinner out, and where.
  out: {
    dinner: 'Dinner out',
    lunch: 'Lunch out',
    where: 'Where? (optional)',
    decide: 'Mom or Dad decide',
    planIt: 'Plan it',
    save: 'Save',
    ask: 'Ask',
    // How the meal reads wherever a meal shows: "Out · Taqueria Luna", or "Out".
    label: (place: string | null | undefined) => (place ? `Out · ${place}` : 'Out'),
    // The NIGHT pack list names the meal: "Dinner out · Taqueria Luna".
    pack: (place: string | null | undefined) => (place ? `Dinner out · ${place}` : 'Dinner out'),
    asks: (who: string, place: string | null | undefined) =>
      `${who} asks: dinner out${place ? ` · ${place}` : ''}`,
    digest: (days: string[]) => `Out: ${days.join(' · ')}`,
  },
  shop: {
    title: 'What your points can be',
    back: 'Back',
    // Said as the question it is: a child is asking, not buying.
    confirm: (name: string, cost: number) => `Ask for ${name} for ${cost} points?`,
    yes: 'Ask',
    no: 'Not now',
    asked: 'Asked',
    approved: 'Yes!',
    done: 'Done',
    // Asked again while the first is still waiting: how many are waiting.
    askedCount: (count: number) => `Asked · ${count}`,
    // Where a cash or Roblox reward goes, said on its tile.
    toPiggy: (amount: string) => `${amount} → piggy bank`,
    toRoblox: (amount: string) => `${amount} → Roblox bank`,
    declined: 'Not this time',
    comingSoon: 'Coming soon',
    // The star on a tile. Said as what it does, not as a verb: a child is
    // marking a thing they want, not filing a request.
    save: 'Save for this',
    saving: 'Saving for this',
    // The shop opens on what a child can actually have; everything else is
    // one tap away. A wall of things you cannot afford is not a shop.
    showAll: 'Show everything',
    showAffordable: 'Show what I can get',
    shortfall: (points: number) => `${points} more`,
    nothingAffordable: 'Nothing yet — keep earning.',
    // The line above the grid on a morning with nothing in the balance. Two
    // real numbers from this child's own list, because "keep earning" is
    // advice and "Homework is 10 points" is a plan.
    nudge: (task: string, earn: number, reward: string, cost: number) =>
      `${task} is ${earn} points. ${reward} is ${cost}.`,
    mine: 'What I asked for',
    noneYet: 'Nothing yet.',
    askedFor: (name: string) => `Asked for ${name}. Mom or Dad will say.`,
    notYet: 'That did not go through.',
    jarHas: (points: number) => `Jar has ${points}`,
    jarTitle: 'The family jar',
    jarWhat: 'Points in the jar buy things the whole family does.',
    jarGive: (points: number) => `Put in ${points}`,
    jarDone: (points: number) => `${points} points in the jar. Thank you.`,
  },

  meals: {
    breakfast: 'Breakfast',
    lunch: 'Lunch',
    dinner: 'Dinner',
    snack: 'Snack',
    none: 'No meals planned',
    empty: '—',
    vegDay: 'Veg day',
    kidsEat: (protein: string) => `Kids eat ${protein}`,
  },

  tomorrow: {
    label: 'Tomorrow',
    nothing: 'Nothing scheduled',
    // The two ways tomorrow is not an ordinary school day that the head has
    // room to say. A minimum day is recognised from the school's own note.
    noSchool: 'No school',
    minimumDay: 'Minimum day',
    events: (count: number) => (count === 1 ? '1 event' : `${count} events`),
  },

  feelings: {
    // Asked once, at bedtime, and never asked again. No question mark: it is
    // an offer, not a form.
    title: 'How was today',
    faces: {
      great: 'Great',
      good: 'Good',
      okay: 'Okay',
      meh: 'Meh',
      rough: 'Rough',
    } as Record<string, string>,
    thanks: 'Thank you',
  },

  night: {
    today: 'Today',
    tomorrow: 'Tomorrow',
    pack: 'Pack',
    nothingPacked: 'Nothing packed yet',
    nothingTomorrow: 'Nothing on for tomorrow',
    nothing: 'Nothing scheduled',
    family: 'Family',
  },

  stale: {
    since: (time: string) => `since ${time}`,
  },

  // The one keypad, for a parent's PIN and a kid's code.
  keypad: {
    yourCode: 'Your code',
    // A kid's wrong code: no count, no lockout, just another go.
    tryAgain: 'Try again',
    open: 'Open',
  },

  parent: {
    title: 'Parents only',
    // The word on the pill in the corner of DAY and NIGHT. "Parents", not
    // "Settings": it says who it is for rather than what is behind it.
    pill: 'Parents',
    modeOn: 'Parent mode',
    showDashboard: 'Show the dashboard',
    // The phone opens here, so it says whose screen this is before the PIN.
    phoneTitle: 'Mantel Parents',
    tabs: {
      approvals: 'Approvals',
      meals: 'Meals',
      events: 'Events',
      photos: 'Photos',
      points: 'Points',
      settings: 'Settings',
    },
    // Settings is a long page; the groups are what make it scannable.
    groups: {
      night: 'Night and idle',
      photos: 'Photos',
      calendars: 'Calendars',
      diet: 'Diet',
      kids: 'Kids',
      about: 'About and diagnostics',
    },
    cancel: 'Cancel',
    open: 'Open',
    clear: 'Clear',
    loading: 'Loading…',
    wait: (seconds: number) => `Wait ${seconds}s`,
    // A wrong PIN, said as what to do next and how many goes are left.
    enterPin: 'Enter the PIN',
    tryAgain: (left: number) => `Try again · ${left} left`,
    lockedFor: (seconds: number) => `Too many tries. Wait ${seconds}s.`,
    noPinSet: 'No PIN is set on the API.',
    apiSilent: 'The API did not answer.',
    thingsWaiting: (count: number) =>
      count === 1 ? '1 thing is waiting' : `${count} things are waiting`,
    backspace: 'Delete a digit',
    digitsEntered: (count: number) => `${count} of 4 digits entered`,

    // The rail. Each section is a row with a glyph; below 900px the same
    // sections are a bar of glyphs along the bottom.
    sections: {
      approvals: { title: 'Approvals', description: 'What the children are waiting on.' },
      meals: { title: 'Meals', description: 'The week. Edit: tap any meal to change it.' },
      events: {
        title: 'Events',
        description: 'Where the calendar comes from, and which school events reach the wall.',
      },
      photos: { title: 'Photos', description: '' },
      points: { title: 'Points', description: 'Where each child stands, and how they got there.' },
      settings: { title: 'Settings', description: 'Changes save as you make them.' },
      about: { title: 'About', description: '' },
    } as Record<string, { title: string; description: string }>,
    rail: {
      // family.yaml has no name for the family, and this does not make one up.
      family: 'Our family',
      session: (minutes: number) => `Parent mode · ${minutes} min`,
      waiting: (count: number) => (count === 1 ? '1 waiting' : `${count} waiting`),
    },
    ui: {
      close: 'Close',
      less: (label: string) => `Less: ${label}`,
      more: (label: string) => `More: ${label}`,
    },

    approvals: {
      award: 'Award',
      approve: 'Approve',
      decline: 'Decline',
      paid: 'Paid',
      nothing: 'Nothing waiting',
      meals: 'Meals',
      parentsDecide: 'Parents decide',
      todoTitle: 'To do for you',
      failed: 'That did not go through.',
      chore: (title: string, points: number) => `${title} · +${points}`,
      reward: (title: string, points: number) => `${title} · ${points} pts`,
      approvedClaim: (title: string, who: string, balance: number) =>
        `${title} approved. ${who} has ${balance} points.`,
      declined: (title: string) => `${title}: not today.`,
      approvedReward: (title: string, who: string) => `${title} approved for ${who}.`,
      refunded: (title: string, who: string) => `${title} declined. ${who} has the points back.`,
      allowance: (day: number, days: number, who: string) =>
        `Allowance day ${day} of ${days} for ${who}`,
      todo: (title: string, who: string) => `${title} for ${who}`,
      giveCash: (who: string, dollars: number) => `Give ${who} $${dollars}`,
      due: (date: string) => `due ${date}`,
      // "Thu dinner", from the API's date and slot.
      slotOn: (date: string, slot: string) => {
        const [year, month, day] = date.split('-').map(Number)
        const weekday = new Date(year, month - 1, day).toLocaleDateString('en-US', {
          weekday: 'short',
        })
        return `${weekday} ${slot}`
      },
      insteadOf: (when: string, plan: string) => `${when} · instead of ${plan}`,
      usePlan: (plan: string) => `Use the plan · ${plan}`,
      mealYes: (dish: string) => `${dish} it is.`,
      // The decide card's three answers, and what it says once decided.
      kidsPick: (name: string) => `${name}’s`,
      alternate: 'Alternate',
      outcomeChose: (name: string, dish: string, weekday: string) =>
        `${name}’s ${dish}, ${weekday}.`,
      outcomeAlternate: (winner: string, day: string, other: string, otherDay: string) =>
        `${winner}’s on ${day}, ${other}’s on ${otherDay}.`,
      noDay: 'no free day in the next month',
      mealPlan: 'Back to the plan.',
    },

    award: {
      title: 'Award points',
      who: 'Who',
      forWhat: 'What it was for',
      placeholder: 'Helped with the reading at bedtime',
      howMany: 'How many points',
      give: 'Award',
      take: 'Take away',
      said: (points: number, who: string, balance: number) =>
        points > 0
          ? `${points} points to ${who}. They have ${balance}.`
          : `${Math.abs(points)} points from ${who}. They have ${balance}.`,
    },

    meals: {
      fromToday: 'From today',
      today: 'Today',
      weekOf: (head: string) => `From ${head}`,
      // An empty cell: still a button, and says so by being one.
      empty: '—',
      previous: 'Previous week',
      next: 'Next week',
      nothing: 'Nothing planned',
      usePlan: 'Use the plan',
      failed: 'Could not read the meals.',
      cellLabel: (day: string, slot: string, dish: string) => `${day}, ${slot}: ${dish}`,
      sheetTitle: (day: string, slot: string) => `${day} · ${slot}`,
    },

    points: {
      adjust: 'Adjust',
      balance: 'Balance',
      thisWeek: 'This week',
      streak: 'Streak',
      days: (n: number) => (n === 1 ? '1 day' : `${n} days`),
      ledger: 'The last thirty',
      filter: 'Show',
      everyone: 'Everyone',
      none: 'Nothing yet.',
      columns: { date: 'Date', what: 'What', delta: 'Points', who: 'Who' },
      // Putting a wrong row right (corrections.py): new rows, never an edit.
      fix: 'Fix',
      fixTitle: 'Put this right',
      fixed: 'Put right',
      undoTake: (points: number) => `Undo · take ${points} back`,
      undoGive: (points: number) => `Undo · give ${points} back`,
      undoChore: 'The chore goes back to not done, and can be claimed again.',
      moveTo: (name: string) => `Move to ${name}`,
      notFixed: (why: string) => `Not changed: ${why}`,
      why: {
        task: 'Chore',
        award: 'Award',
        redeem: 'Reward',
        refund: 'Refund',
        adjust: 'Adjustment',
        jar: 'Jar',
      } as Record<string, string>,
      actor: { kid: 'Kid', parent: 'Parent' } as Record<string, string>,
      digest: (start: string, end: string) => `This week · ${start} to ${end}`,
      earned: (earned: number, spent: number) =>
        spent > 0 ? `${earned} earned, ${spent} spent` : `${earned} earned`,
      noChores: 'No chores approved yet.',
      cashOwed: 'Cash owed',
      nothingOwed: 'Nothing owed',
      dollars: (n: number) => `$${n}`,
      // Owed is paid from its card in Approvals; this says where.
      payFromApprovals: 'Paid from To do for you',
      paidCash: (n: number, when: string) => `$${n} cash · paid · ${when}`,
      rewards: (names: string[]) => `Rewards: ${names.join(' · ')}`,
      picked: (names: string[]) => `Picked: ${names.join(' · ')}`,
    },

    events: {
      calendars: 'Calendars',
      refresh: 'Refresh',
      refreshing: 'Refreshing…',
      refreshed: 'Weather and calendars fetched again.',
      refreshFailed: 'The refresh did not go through.',
      // What the common feeds are called here, when settings.yaml gives no
      // name. A child's feed is their name; a school's is its `name:`.
      feeds: {
        family: 'Family',
        us_holidays: 'US holidays',
        india_holidays: 'Indian festivals',
        hindu_holidays: 'Hindu festivals',
      } as Record<string, string>,
      states: {
        ok: 'Working',
        stale: 'Stale',
        error: 'Failing',
        not_configured: 'Not set up',
        never: 'Waiting',
      } as Record<string, string>,
      fetched: (age: string, detail: string) =>
        detail ? `last fetched ${age} · ${detail}` : `last fetched ${age}`,
      never: 'not fetched yet',
      addSecret: (env: string) => `Add the secret iCal URL to .env as ${env}`,
      notSetUp: 'No URL yet',
      schoolTitle: 'School events',
      help: 'The school feeds carry everything the schools do. Choose who sees what.',
      unmatched: 'Show series nobody has chosen',
      search: 'Search events',
      count: (n: number) => `${n} ${n === 1 ? 'time' : 'times'}`,
      next: (when: string) => `next ${when}`,
      always: 'Always shown',
      showTo: (title: string, name: string) => `${title}, shown to ${name}`,
      none: 'No school events in the next 60 days',
      failed: 'Could not read the school feeds',
    },

    photos: {
      description: (count: number, size: string) =>
        `${count} ${count === 1 ? 'photo' : 'photos'} · ${size}`,
      shortcutTitle: 'Adding photos',
      // Three lines, in the order a parent does them on the phone.
      shortcut: [
        'On the iPhone, put photos in the Photos album “Mantel”.',
        'Run the Shortcut “Send to Mantel”; it sends them with the upload token.',
        'They appear here and in the frame. Setup is in docs/photos.md.',
      ],
      token: 'Upload token',
      tokenSet: 'Set',
      tokenMissing: 'Not set — add MANTEL_UPLOAD_TOKEN to .env',
      none: 'Nothing uploaded yet.',
      noneShortcut: 'Run the Shortcut “Send to Mantel” on the iPhone to add some.',
      open: (when: string) => (when ? `Photo from ${when}` : 'Photo'),
      undated: 'Photo',
      delete: 'Delete',
      sure: 'Delete this photo?',
      deleted: 'Photo deleted.',
    },

    settings: {
      saved: 'Saved',
      notSaved: (why: string) => `Not saved: ${why}`,
      failed: 'Could not load the settings.',
      groups: {
        night: 'Night and idle',
        photos: 'Photos',
        calendars: 'Calendars',
        diet: 'Diet',
        kids: 'Kids',
        points: 'Points',
      },
      nightStart: 'Night starts',
      nightEnd: 'Night ends',
      idle: 'Idle minutes',
      idleNote: 'Before the photo frame takes over by day',
      nightIdle: 'Night idle minutes',
      frameAtNight: 'Photo frame at night',
      slide: 'Seconds per photo',
      frameChip: 'Clock and weather on the frame',
      chipSize: 'Chip size',
      chipSizes: { regular: 'Regular', large: 'Large' },
      refresh: 'Refresh minutes',
      refreshNote: 'How often the calendars are fetched',
      nonVegDays: 'Non-veg days',
      nonVegNote: 'The weekdays the children may have meat, fish or egg',
      nonVegOn: (day: string) => `Non-veg on ${day}`,
      weekdays: {
        mon: 'Mon',
        tue: 'Tue',
        wed: 'Wed',
        thu: 'Thu',
        fri: 'Fri',
        sat: 'Sat',
        sun: 'Sun',
      } as Record<string, string>,
      festivalsHead: 'Festivals',
      festivalsLead: 'Vegetarian on these festivals and the days after them.',
      festivalNote: 'Days, counting the festival itself',
      days: (n: number) => (n === 1 ? 'day' : 'days'),
      extraDates: 'Extra veg dates',
      extraNote: 'For the festivals no calendar carries',
      extraName: 'Name',
      from: 'From',
      to: 'To',
      add: 'Add',
      remove: (name: string) => `Remove ${name}`,
      removeShort: 'Remove',
      name: 'Name',
      avatar: 'Animal',
      chooseAvatar: (name: string) => `Choose ${name}’s animal`,
      colour: 'Colour',
      pin: 'Card code',
      pinOn: 'Set: their card asks for it',
      pinOff: 'None: their card opens with a tap',
      setPin: 'Set',
      clearPin: 'Clear',
      pinSet: 'Code set.',
      pinCleared: 'Code cleared.',
      streakBonus: 'Streak bonus',
      streakBonusNote: 'Paid once for a full streak',
      streakDays: 'Streak length',
      roblox: 'Roblox per week',
      deductions: 'Allow taking points away',
      deductionsNote: 'Adds −5 and −10 to Adjust. Never below zero.',
      parentIdle: 'Parent mode closes after',
      min: 'min',
      sec: 'sec',
      pts: 'pts',
    },

    about: {
      version: (version: string) => `Mantel ${version}`,
      health: 'Health',
      ok: 'OK',
      notOk: 'Check',
      weather: 'Weather',
      calendar: (name: string) => `Calendar · ${name}`,
      ledger: 'Ledger',
      schoolYear: 'School year',
      dietDays: 'Diet days',
      secondIpad: 'The second iPad',
      lanUrl: 'Open this address',
      lanNote: 'Or point the iPad’s camera at the code.',
      qr: (url: string) => `QR code for ${url}`,
      tools: 'When something is off',
      reload: 'Reload both iPads',
      reloadNote: 'Each reloads the next time it checks in, within a few minutes',
      reloadShort: 'Reload',
      reloadAsked: 'Both iPads will reload within a few minutes.',
      diagnostics: 'Diagnostics',
      diagnosticsNote: 'Everything the kiosk knows about itself',
      open: 'Open',
      service: 'Service',
    },
    done: 'Done',
  },

  month: {
    done: 'Done',
    panchang: 'Panchang',
    previous: 'Previous month',
    next: 'Next month',
    tithi: 'Tithi',
    nakshatra: 'Nakshatra',
    yoga: 'Yoga',
    karana: 'Karana',
    sunrise: 'Sunrise',
    sunset: 'Sunset',
    moonrise: 'Moonrise',
    schoolDay: 'School day',
    noSchool: 'No school',
    vegDay: 'Veg day',
    // The day panel's second line and its facts.
    samvat: (masa: string, adhika: boolean, vikram: number) =>
      `${masa}${adhika ? ' (Adhika)' : ''} · Vikram Samvat ${vikram}`,
    until: (time: string) => `to ${time}`,
    vegBecause: (reasons: string[]) => `veg day · ${reasons.join(' · ')}`,
    kidsEat: (protein: string) => `Kids eat ${protein}`,
    weekdays: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    // The tithi in a cell narrowed by the day panel: short enough that the
    // paksha's half moon always fits beside it, and never an ellipsis.
    tithiShort: {
      Pratipada: 'Prati',
      Dwitiya: 'Dwiti',
      Tritiya: 'Triti',
      Chaturthi: 'Chatur',
      Panchami: 'Pancha',
      Shashthi: 'Shash',
      Saptami: 'Sapta',
      Ashtami: 'Ashta',
      Navami: 'Nava',
      Dashami: 'Dasha',
      Ekadashi: 'Ekad',
      Dwadashi: 'Dwad',
      Trayodashi: 'Trayo',
      Chaturdashi: 'Chaturd',
      Purnima: 'Purnima',
      Amavasya: 'Amavas',
    } as Record<string, string>,
    // The row under the grid that says what the marks mean.
    legend: {
      family: 'Family',
      school: 'No school',
      festival: 'Festival',
      holiday: 'Holiday',
      veg: 'Veg',
      newMoon: 'New moon',
      fullMoon: 'Full moon',
    },
    // What a 90px cell calls the observances this family actually keeps.
    // The feeds write them long and inconsistently — "First Day of Sharad
    // Navratri", "Maharishi Valmiki Jayanti", "Karaka Chaturthi" — and no
    // rule derived from the string gets all of them right. These are the
    // ones worth naming by hand; anything else is shortened by rule.
    short: {
      'first day of sharad navratri': 'Navratri',
      navratri: 'Navratri',
      dussehra: 'Dussehra',
      diwali: 'Diwali',
      holi: 'Holi',
      halloween: 'Halloween',
      thanksgiving: 'Thanksgiving',
      christmas: 'Christmas',
      'columbus day': 'Columbus Day',
      'mahatma gandhi jayanti': 'Gandhi Jayanti',
      'first day of durga puja festivities': 'Durga Puja',
      'durga puja festivities': 'Durga Puja',
      'maha saptami': 'Saptami',
      'maha ashtami': 'Ashtami',
      'karaka chaturthi': 'Karwa Chauth',
      'maharishi valmiki jayanti': 'Valmiki Jayanti',
    } as Record<string, string>,
  },

  list: {
    month: 'Month',
    list: 'List',
    done: 'Done',
    all: 'All',
    allDay: 'All day',
    nothing: 'Nothing in the next 60 days',
    // The shared chips. A child's chip is their name, from the config.
    filters: {
      family: 'Family',
      school: 'School',
      festival: 'Festivals',
      holiday: 'Holidays',
    } as Record<string, string>,
  },

  frame: {
    noPhotos: 'No photos yet',
    // The chip over the photo: today's high and low, or at night tomorrow's.
    range: (high: string, low: string) => `${high} / ${low}`,
    tomorrow: (high: string, low: string) => `Tomorrow ${high} / ${low}`,
  },
} as const
