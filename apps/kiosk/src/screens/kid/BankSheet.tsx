import { useEffect, useState } from 'react'

import { askCashOut, askRobloxTime, getBank } from '../../api/points'
import type { BankAccount, KidBank } from '../../api/types'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { amountOf, cashOutOffer, dollars, duration, robloxOk, rowLine } from './bank'

/** How many of the account's rows the sheet lists. */
const ROWS = 10

/** What a tap is asking for, held on the sheet until the child says Ask. */
type Asking = { account: BankAccount; amount: number }

/**
 * One of a child's two banks: what is in it, what happened to it lately, and
 * the one way to take something out.
 *
 * Taking out is asking. The amount is held the moment the child asks and
 * leaves the bank only when Mom or Dad has handed it over, so the sheet says
 * the balance, what is still free to ask for, and that it is waiting.
 */
export default function BankSheet({
  kidId,
  account,
  onDone,
  onChanged,
}: {
  kidId: string
  account: BankAccount
  onDone: () => void
  onChanged: () => void
}) {
  const [bank, setBank] = useState<KidBank | null>(null)
  const [asking, setAsking] = useState<Asking | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    let cancelled = false
    getBank(kidId)
      .then((loaded) => {
        if (!cancelled) {
          setBank(loaded)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [kidId])

  const ask = (wanted: Asking) => {
    setBusy(true)
    const sent =
      wanted.account === 'cash'
        ? askCashOut(kidId, wanted.amount)
        : askRobloxTime(kidId, wanted.amount)
    sent
      .then((updated) => {
        setBank(updated)
        setNote('')
        onChanged()
      })
      .catch(() => setNote(copy.bank.notYet))
      .finally(() => {
        setAsking(null)
        setBusy(false)
      })
  }

  const title = account === 'cash' ? copy.bank.piggy : copy.bank.roblox
  const held = bank ? (account === 'cash' ? bank.cash : bank.roblox) : null
  const balance = bank ? (account === 'cash' ? bank.cash.cents : bank.roblox.minutes) : 0
  const free = bank
    ? account === 'cash'
      ? bank.cash.available_cents
      : bank.roblox.available_minutes
    : 0
  const waiting = (held?.pending.length ?? 0) > 0
  const rows = (bank?.recent ?? []).filter((row) => row.account === account).slice(0, ROWS)

  let action = null
  if (bank && asking) {
    const what =
      asking.account === 'cash'
        ? dollars(asking.amount)
        : copy.bank.robloxOf(duration(asking.amount))
    action = (
      <div className="bank-ask">
        <p className="bank-question">{copy.bank.askFor(what)}</p>
        <div className="confirm-actions">
          <button
            type="button"
            className="decide decide-yes"
            disabled={busy}
            onClick={() => ask(asking)}
          >
            {copy.bank.ask}
          </button>
          <button type="button" className="decide" disabled={busy} onClick={() => setAsking(null)}>
            {copy.bank.notNow}
          </button>
        </div>
      </div>
    )
  } else if (bank && account === 'cash' && !(waiting && !cashOutOffer(bank).ok)) {
    // While a cash-out waits, "Save $20 more" would be the held money said as
    // missing: the sheet says it is asked for, and offers more only if there is.
    const offer = cashOutOffer(bank)
    action = (
      <div className="bank-ask">
        <button
          type="button"
          className="decide decide-yes bank-out"
          disabled={!offer.ok || busy}
          onClick={() => setAsking({ account: 'cash', amount: offer.cents })}
        >
          {copy.bank.cashOut(dollars(offer.cents))}
        </button>
        {offer.ok ? null : <p className="bank-note">{copy.bank.saveMore(dollars(offer.short))}</p>}
      </div>
    )
  } else if (bank && account === 'roblox') {
    action = (
      <div className="bank-ask">
        <div className="choices choices-centre">
          {bank.roblox.sizes.map((minutes) => (
            <button
              key={minutes}
              type="button"
              className="choice bank-size"
              disabled={!robloxOk(bank, minutes) || busy}
              onClick={() => setAsking({ account: 'roblox', amount: minutes })}
            >
              {duration(minutes)}
            </button>
          ))}
        </div>
        <p className="bank-note">
          {copy.bank.ofWeek(bank.roblox.uses_this_week, bank.roblox.per_week)}
        </p>
      </div>
    )
  }

  return (
    <div className="confirm">
      <div className="confirm-card bank-sheet" data-bank={account}>
        <div className="bank-head">
          <p className="bank-title">
            <Icon name={account === 'cash' ? 'piggy' : 'game'} size={24} className="bank-glyph" />
            {title}
          </p>
          <p className="bank-balance">{amountOf(account, balance)}</p>
        </div>

        <div className="bank-side">
          {waiting ? (
            <>
              <p className="bank-note">{copy.bank.available(amountOf(account, free))}</p>
              <p className="bank-note bank-waiting">{copy.bank.asked}</p>
            </>
          ) : null}
          {action}
          {note ? <p className="bank-note">{note}</p> : null}
        </div>

        {/* What happened to it lately, as plain lines: the last ten. */}
        {rows.length === 0 ? (
          <p className="bank-note bank-history">{copy.bank.nothingYet}</p>
        ) : (
          <ul className="bank-rows bank-history">
            {rows.map((row) => (
              <li key={row.id} className="bank-row clamp-1">
                {rowLine(row)}
              </li>
            ))}
          </ul>
        )}

        <div className="confirm-actions bank-close">
          <button type="button" className="decide" onClick={onDone}>
            {copy.bank.done}
          </button>
        </div>
      </div>
    </div>
  )
}
