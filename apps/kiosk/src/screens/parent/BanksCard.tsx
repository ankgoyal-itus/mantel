import { useId, useState } from 'react'

import { adjustBank } from '../../api/parent'
import type { BankAccount, Kid, KidBank } from '../../api/types'
import Avatar from '../../components/Avatar'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import { usePressGuard } from '../../usePressGuard'
import { amountOf } from '../kid/bank'
import { Card, Sheet } from './ui'

/** "Mon 22 Sep". */
function dateSaid(value: string): string {
  const at = new Date(value)
  return Number.isNaN(at.getTime())
    ? ''
    : at.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short' })
}

function signed(account: BankAccount, delta: number): string {
  return `${delta > 0 ? '+' : '−'}${amountOf(account, Math.abs(delta))}`
}

/**
 * One child's two banks, for a parent: what is in each, what is waiting on
 * a parent in Approvals, and the last twenty rows across both — the answer to
 * "where did her twenty dollars go". Adjust is the only way to change it by
 * hand, and it adds a row rather than editing one.
 */
export function BanksCard({
  kid,
  bank,
  onAdjust,
}: {
  kid: Kid
  bank: KidBank
  onAdjust: () => void
}) {
  const accounts: { account: BankAccount; label: string; balance: number; held: number }[] = [
    {
      account: 'cash',
      label: copy.parent.points.piggy,
      balance: bank.cash.cents,
      held: bank.cash.cents - bank.cash.available_cents,
    },
    {
      account: 'roblox',
      label: copy.parent.points.roblox,
      balance: bank.roblox.minutes,
      held: bank.roblox.minutes - bank.roblox.available_minutes,
    },
  ]
  return (
    <Card className="pp-bank-card">
      <div className="pp-bank-head">
        <h2 className="pp-group-head" style={kidVars(kid.id, kid.color)}>
          <Avatar name={kid.name} avatar={kid.avatar} size={24} />
          <span>{copy.parent.points.banksOf(kid.name)}</span>
        </h2>
        <button type="button" className="pp-button" onClick={onAdjust}>
          {copy.parent.points.adjustBank}
        </button>
      </div>
      <dl className="pp-stats">
        {accounts.map((one) => (
          <div key={one.account}>
            <dt>{one.label}</dt>
            <dd>{amountOf(one.account, one.balance)}</dd>
            {one.held > 0 ? (
              <dd className="pp-bank-held">
                {copy.parent.points.held(amountOf(one.account, one.held))}
              </dd>
            ) : null}
          </div>
        ))}
      </dl>
      {accounts.some((one) => one.held > 0) ? (
        <p className="pp-line pp-muted">{copy.parent.points.waitingIn}</p>
      ) : null}
      {bank.recent.length === 0 ? (
        <p className="pp-muted">{copy.parent.points.bankNone}</p>
      ) : (
        <table className="pp-table">
          <thead>
            <tr>
              <th scope="col">{copy.parent.points.bankColumns.date}</th>
              <th scope="col">{copy.parent.points.bankColumns.what}</th>
              <th scope="col" className="pp-num">
                {copy.parent.points.bankColumns.amount}
              </th>
              <th scope="col">{copy.parent.points.bankColumns.who}</th>
            </tr>
          </thead>
          <tbody>
            {bank.recent.map((row) => (
              <tr key={row.id}>
                <td className="pp-nowrap">{dateSaid(row.created_at)}</td>
                <td>{row.note || copy.parent.points.bankWhy[row.reason_kind]}</td>
                <td className={row.delta < 0 ? 'pp-num pp-spent' : 'pp-num pp-earned'}>
                  {signed(row.account, row.delta)}
                </td>
                <td>{copy.parent.points.bankActor[row.actor]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

/** What a parent puts in or takes out by hand, in each bank's own units. */
const AMOUNTS: Record<BankAccount, number[]> = {
  cash: [100, 500, 1000, 2000],
  roblox: [15, 30, 60, 120],
}

/**
 * Birthday money, or a correction. Which bank, which way, how much, and what
 * for — the note is required, because "$20" six weeks later means nothing
 * without it.
 */
export function BankAdjustSheet({
  kid,
  onClose,
  onSaved,
}: {
  kid: Kid
  onClose: () => void
  onSaved: (said: string) => void
}) {
  const [account, setAccount] = useState<BankAccount>('cash')
  const [sign, setSign] = useState<1 | -1>(1)
  const [amount, setAmount] = useState(AMOUNTS.cash[1])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const guard = usePressGuard()
  const noteId = useId()

  const choose = (next: BankAccount) => {
    setAccount(next)
    setAmount(AMOUNTS[next][1])
  }

  const save = () => {
    if (!note.trim()) {
      return
    }
    setBusy(true)
    setError('')
    const delta = sign * amount
    adjustBank(kid.id, account, delta, note.trim())
      .then(() => {
        onSaved(copy.parent.points.bankSaved(kid.name, `${signed(account, delta)} · ${note.trim()}`))
        onClose()
      })
      .catch((failure: Error) => setError(failure.message || copy.parent.approvals.failed))
      .finally(() => setBusy(false))
  }

  return (
    <Sheet title={copy.parent.points.adjustTitle(kid.name)} onClose={onClose}>
      <div className="pp-chips" role="radiogroup" aria-label={copy.parent.points.account}>
        {(['cash', 'roblox'] as const).map((one) => (
          <button
            key={one}
            type="button"
            role="radio"
            aria-checked={one === account}
            className={one === account ? 'pp-chip pp-chip-on' : 'pp-chip'}
            onClick={() => choose(one)}
          >
            {one === 'cash' ? copy.parent.points.piggy : copy.parent.points.roblox}
          </button>
        ))}
      </div>

      <div
        className="pp-chips"
        role="radiogroup"
        aria-label={`${copy.parent.points.putIn} · ${copy.parent.points.takeOut}`}
      >
        {([1, -1] as const).map((way) => (
          <button
            key={way}
            type="button"
            role="radio"
            aria-checked={way === sign}
            className={way === sign ? 'pp-chip pp-chip-on' : 'pp-chip'}
            onClick={() => setSign(way)}
          >
            {way > 0 ? copy.parent.points.putIn : copy.parent.points.takeOut}
          </button>
        ))}
      </div>

      <div className="pp-chips" role="radiogroup" aria-label={copy.parent.points.howMuch}>
        {AMOUNTS[account].map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={value === amount}
            className={value === amount ? 'pp-chip pp-chip-on' : 'pp-chip'}
            onClick={() => setAmount(value)}
          >
            {amountOf(account, value)}
          </button>
        ))}
      </div>

      <label className="pp-field" htmlFor={noteId}>
        <span className="pp-row-label">{copy.parent.points.bankFor}</span>
        <input
          id={noteId}
          className="pp-input"
          type="text"
          maxLength={80}
          value={note}
          placeholder={copy.parent.points.bankPlaceholder}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      {error ? <p className="pp-bad">{error}</p> : null}

      <div className="pp-sheet-actions">
        <button
          type="button"
          className="pp-button pp-button-accent"
          disabled={busy || !note.trim()}
          data-pressed={guard.pressed === 'save' ? 'yes' : undefined}
          onClick={() => guard.press('save', save)}
        >
          {`${copy.parent.points.bankSave} · ${signed(account, sign * amount)}`}
        </button>
      </div>
    </Sheet>
  )
}
