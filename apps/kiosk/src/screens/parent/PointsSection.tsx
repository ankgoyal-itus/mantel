import { useEffect, useState } from 'react'

import { useLiveNonce } from '../../api/live'
import { getJson } from '../../api/client'
import { correctRow, getDigest, getLedger, getPayouts } from '../../api/parent'
import type { Digest, Kid, LedgerRow, Payout, PointsSummary } from '../../api/types'
import Avatar from '../../components/Avatar'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { kidVars } from '../../kidVars'
import { usePressGuard } from '../../usePressGuard'
import AwardSheet from './AwardSheet'
import { Card, Pane, Row, Sheet, Toast } from './ui'

/** The rows a parent reads back through, and no more: this is a glance. */
const LEDGER_ROWS = 30

/** "Mon 22 Sep". */
function dateSaid(value: string): string {
  const at = new Date(value)
  return Number.isNaN(at.getTime())
    ? ''
    : at.toLocaleDateString('en-US', { weekday: 'short', day: 'numeric', month: 'short' })
}

/**
 * Where each child stands, and how they got there.
 *
 * Three numbers per child, then the ledger as a plain table: when, what,
 * how much, and who did it — the answer to "where did thirty points go".
 * The week's digest sits under it, because it is the same question asked
 * of seven days at once.
 */
export default function PointsSection({
  kids,
  onPointsChanged,
}: {
  kids: Kid[]
  onPointsChanged?: () => void
}) {
  const [summaries, setSummaries] = useState<Record<string, PointsSummary>>({})
  const [rows, setRows] = useState<LedgerRow[] | null>(null)
  const [digest, setDigest] = useState<Digest | null>(null)
  const [only, setOnly] = useState<string | null>(null)
  const [adjusting, setAdjusting] = useState(false)
  const [own, setNonce] = useState(0)
  // What this screen did, and what another screen did: both refetch.
  const nonce = own + useLiveNonce()
  const [note, setNote] = useState('')
  const [bad, setBad] = useState(false)
  // The row being put right, in its sheet.
  const [fixing, setFixing] = useState<LedgerRow | null>(null)
  const guard = usePressGuard()

  const fix = (row: LedgerRow, action: 'undo' | 'move', toKid?: string) => {
    guard.press(`${row.id}:${action}:${toKid ?? ''}`, () => {
      correctRow(row.id, action, toKid)
        .then(() => {
          setFixing(null)
          setBad(false)
          setNote(copy.parent.points.fixed)
          setNonce((count) => count + 1)
          onPointsChanged?.()
        })
        .catch((error: unknown) => {
          setFixing(null)
          setBad(true)
          setNote(copy.parent.points.notFixed(error instanceof Error ? error.message : ''))
        })
    }, `fix:${row.id}`)
  }

  useEffect(() => {
    let cancelled = false
    for (const kid of kids) {
      getJson<PointsSummary>(`/api/points/${kid.id}`)
        .then((summary) => !cancelled && setSummaries((all) => ({ ...all, [kid.id]: summary })))
        .catch(() => undefined)
    }
    getDigest()
      .then((found) => !cancelled && setDigest(found))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [kids, nonce])

  useEffect(() => {
    let cancelled = false
    getLedger(only ?? undefined, LEDGER_ROWS)
      .then((found) => !cancelled && setRows(found))
      .catch(() => !cancelled && setRows([]))
    return () => {
      cancelled = true
    }
  }, [only, nonce])

  const nameOf = (id: string) => kids.find((kid) => kid.id === id)?.name ?? id

  return (
    <Pane
      title={copy.parent.sections.points.title}
      description={copy.parent.sections.points.description}
      action={
        <button type="button" className="pp-button" onClick={() => setAdjusting(true)}>
          <Icon name="coin" size={20} />
          {copy.parent.points.adjust}
        </button>
      }
    >
      <div className="pp-kid-cards">
        {kids.map((kid) => {
          const summary = summaries[kid.id]
          return (
            <Card key={kid.id} className="pp-kid-card">
              <h2 className="pp-group-head" style={kidVars(kid.id, kid.color)}>
                <Avatar name={kid.name} avatar={kid.avatar} size={24} />
                <span>{kid.name}</span>
              </h2>
              <dl className="pp-stats">
                <div>
                  <dt>{copy.parent.points.balance}</dt>
                  <dd>{summary ? summary.balance : '—'}</dd>
                </div>
                <div>
                  <dt>{copy.parent.points.thisWeek}</dt>
                  <dd>{summary ? summary.this_week : '—'}</dd>
                </div>
                <div>
                  <dt>{copy.parent.points.streak}</dt>
                  <dd>{summary ? copy.parent.points.days(summary.streak_days) : '—'}</dd>
                </div>
              </dl>
              <CashRow kidId={kid.id} owed={summary?.dollars_owed ?? 0} nonce={nonce} />
            </Card>
          )
        })}
      </div>

      <Card title={copy.parent.points.ledger}>
        <div className="pp-chips" role="radiogroup" aria-label={copy.parent.points.filter}>
          {[null, ...kids.map((kid) => kid.id)].map((id) => (
            <button
              key={id ?? 'all'}
              type="button"
              role="radio"
              aria-checked={only === id}
              className={only === id ? 'pp-chip pp-chip-on' : 'pp-chip'}
              onClick={() => setOnly(id)}
            >
              {id ? nameOf(id) : copy.parent.points.everyone}
            </button>
          ))}
        </div>
        {rows === null ? (
          <p className="pp-muted">{copy.parent.loading}</p>
        ) : rows.length === 0 ? (
          <p className="pp-muted">{copy.parent.points.none}</p>
        ) : (
          <table className="pp-table">
            <thead>
              <tr>
                <th scope="col">{copy.parent.points.columns.date}</th>
                <th scope="col">{copy.parent.points.columns.what}</th>
                <th scope="col" className="pp-num">
                  {copy.parent.points.columns.delta}
                </th>
                <th scope="col">{copy.parent.points.columns.who}</th>
                <th scope="col" aria-label={copy.parent.points.fix} />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="pp-nowrap">{dateSaid(row.created_at)}</td>
                  <td>
                    {nameOf(row.kid_id)} · {row.note || copy.parent.points.why[row.reason_kind]}
                  </td>
                  <td className={row.delta < 0 ? 'pp-num pp-spent' : 'pp-num pp-earned'}>
                    {row.delta > 0 ? `+${row.delta}` : `−${Math.abs(row.delta)}`}
                  </td>
                  <td>{copy.parent.points.actor[row.actor]}</td>
                  <td>
                    {(row.can ?? []).length > 0 ? (
                      <button type="button" className="pp-text-button" onClick={() => setFixing(row)}>
                        {copy.parent.points.fix}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {digest ? (
        <Card title={copy.parent.points.digest(digest.start, digest.end)}>
          {digest.kids.map((kid) => {
            const days = Object.keys(kid.approved).sort()
            return (
              <div key={kid.kid_id} className="pp-digest">
                <h3 className="pp-row-label">{kid.name}</h3>
                <p className="pp-line">{copy.parent.points.earned(kid.earned, kid.spent)}</p>
                {days.length === 0 ? (
                  <p className="pp-muted">{copy.parent.points.noChores}</p>
                ) : (
                  days.map((day) => (
                    <p key={day} className="pp-line">
                      <span className="pp-muted">{dateSaid(`${day}T12:00:00`)}</span>{' '}
                      {kid.approved[day].join(', ')}
                    </p>
                  ))
                )}
                {kid.redemptions.length > 0 ? (
                  <p className="pp-line">{copy.parent.points.rewards(kid.redemptions)}</p>
                ) : null}
                {kid.picks.length > 0 ? (
                  <p className="pp-line">{copy.parent.points.picked(kid.picks)}</p>
                ) : null}
              </div>
            )
          })}
          {/* The meals eaten out that week, for the whole house. */}
          {digest.out && digest.out.length > 0 ? (
            <p className="pp-line pp-muted">{copy.out.digest(digest.out)}</p>
          ) : null}
        </Card>
      ) : null}

      <Toast text={note} bad={bad} />

      {/* The sheet is the confirmation: it says which row, and each way of
          putting it right is its own button. */}
      {fixing ? (
        <Sheet title={copy.parent.points.fixTitle} onClose={() => setFixing(null)}>
          <p className="pp-line">
            {`${nameOf(fixing.kid_id)} · ${fixing.note || copy.parent.points.why[fixing.reason_kind]} · ${
              fixing.delta > 0 ? `+${fixing.delta}` : `−${Math.abs(fixing.delta)}`
            } · ${dateSaid(fixing.created_at)}`}
          </p>
          {fixing.reason_kind === 'task' ? (
            <p className="pp-line pp-muted">{copy.parent.points.undoChore}</p>
          ) : null}
          <div className="pp-sheet-actions">
            {(fixing.can ?? []).includes('undo') ? (
              <button
                type="button"
                className="pp-button"
                data-pressed={guard.pressed === `${fixing.id}:undo:` ? 'yes' : undefined}
                onClick={() => fix(fixing, 'undo')}
              >
                {fixing.delta > 0
                  ? copy.parent.points.undoTake(fixing.delta)
                  : copy.parent.points.undoGive(Math.abs(fixing.delta))}
              </button>
            ) : null}
            {(fixing.can ?? []).includes('move')
              ? kids
                  .filter((kid) => kid.id !== fixing.kid_id)
                  .map((kid) => (
                    <button
                      key={kid.id}
                      type="button"
                      className="pp-button pp-button-accent"
                      data-pressed={
                        guard.pressed === `${fixing.id}:move:${kid.id}` ? 'yes' : undefined
                      }
                      onClick={() => fix(fixing, 'move', kid.id)}
                    >
                      {copy.parent.points.moveTo(kid.name)}
                    </button>
                  ))
              : null}
          </div>
        </Sheet>
      ) : null}

      {adjusting ? (
        <AwardSheet
          kids={kids}
          title={copy.parent.points.adjust}
          onClose={() => setAdjusting(false)}
          onAwarded={(said) => {
            setBad(false)
            setNote(said)
            setNonce((count) => count + 1)
            onPointsChanged?.()
          }}
        />
      ) : null}
    </Pane>
  )
}

/**
 * What a child's cash rewards come to: owed, which is paid from its card in
 * Approvals ("Give Sam $5", Paid), and what has been, one line a reward.
 */
function CashRow({ kidId, owed, nonce }: { kidId: string; owed: number; nonce: number }) {
  const [paid, setPaid] = useState<Payout[]>([])

  useEffect(() => {
    let cancelled = false
    getPayouts(kidId)
      .then((found) => !cancelled && setPaid(found))
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [kidId, nonce])

  return (
    <div className="pp-cash">
      <Row
        label={copy.parent.points.cashOwed}
        note={
          owed > 0
            ? `${copy.parent.points.dollars(owed)} · ${copy.parent.points.payFromApprovals}`
            : copy.parent.points.nothingOwed
        }
      />
      {paid.slice(0, 3).map((row) => (
        <p key={row.id} className="pp-line pp-muted">
          {copy.parent.points.paidCash(row.dollars, dateSaid(row.paid_at))}
        </p>
      ))}
    </div>
  )
}
