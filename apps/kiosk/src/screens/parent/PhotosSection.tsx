import { useEffect, useState } from 'react'

import { useLiveNonce } from '../../api/live'
import { deletePhoto, getAbout, getPhotos } from '../../api/parent'
import type { Photo } from '../../api/types'
import Icon from '../../components/icons/Icon'
import { copy } from '../../copy'
import { bytesSaid } from './said'
import { Card, Pane, Row, Sheet, Toast } from './ui'

/**
 * What the frame shows, newest first.
 *
 * The card at the top is how photos get here at all — the Shortcut on a
 * phone — and whether the upload token it needs is set. Only whether: the
 * token is a password, and a screen on a kitchen wall does not show one.
 * A photo opens in a sheet, and deleting it is asked twice there, on the
 * same button, so a stray tap in the grid can never lose one.
 */
export default function PhotosSection() {
  const [photos, setPhotos] = useState<Photo[] | null>(null)
  const [token, setToken] = useState<boolean | null>(null)
  const [open, setOpen] = useState<Photo | null>(null)
  const [armed, setArmed] = useState(false)
  const [note, setNote] = useState({ text: '', bad: false })

  // A photo added or taken away on another phone shows here too.
  const live = useLiveNonce()
  useEffect(() => {
    let cancelled = false
    getPhotos()
      .then((found) => !cancelled && setPhotos(found))
      .catch(() => !cancelled && setPhotos([]))
    getAbout()
      .then((about) => !cancelled && setToken(about.upload_token))
      .catch(() => !cancelled && setToken(null))
    return () => {
      cancelled = true
    }
  }, [live])

  const total = (photos ?? []).reduce((sum, photo) => sum + (photo.bytes ?? 0), 0)

  const remove = (photo: Photo) => {
    deletePhoto(photo.id)
      .then(() => {
        setPhotos((current) => (current ?? []).filter((one) => one.id !== photo.id))
        setNote({ text: copy.parent.photos.deleted, bad: false })
        setOpen(null)
      })
      .catch((failure: Error) => setNote({ text: failure.message, bad: true }))
  }

  return (
    <Pane
      title={copy.parent.sections.photos.title}
      description={
        photos === null ? undefined : copy.parent.photos.description(photos.length, bytesSaid(total))
      }
    >
      <Card title={copy.parent.photos.shortcutTitle}>
        {copy.parent.photos.shortcut.map((line) => (
          <p key={line} className="pp-line">
            {line}
          </p>
        ))}
        <Row label={copy.parent.photos.token}>
          <span className={token ? 'pp-state pp-state-ok' : 'pp-state pp-state-not_configured'}>
            {token === null ? '—' : token ? copy.parent.photos.tokenSet : copy.parent.photos.tokenMissing}
          </span>
        </Row>
      </Card>

      {photos !== null && photos.length === 0 ? (
        <Card>
          <p className="empty-drawn pp-empty">
            <Icon name="frame" size={32} className="pp-empty-glyph" />
            <span>
              {copy.parent.photos.none} {copy.parent.photos.noneShortcut}
            </span>
          </p>
        </Card>
      ) : (
        <div className="pp-thumbs">
          {(photos ?? []).map((photo) => (
            <button
              key={photo.id}
              type="button"
              className="pp-thumb"
              aria-label={copy.parent.photos.open(photo.taken_at ?? photo.added_at?.slice(0, 10) ?? '')}
              onClick={() => {
                setArmed(false)
                setOpen(photo)
              }}
            >
              <img src={photo.url} alt="" loading="lazy" draggable={false} />
            </button>
          ))}
        </div>
      )}

      <Toast text={note.text} bad={note.bad} />

      {open ? (
        <Sheet
          title={open.taken_at ?? copy.parent.photos.undated}
          onClose={() => setOpen(null)}
        >
          <img className="pp-preview" src={open.url} alt="" draggable={false} />
          {open.place ? <p className="pp-row-note">{open.place}</p> : null}
          <div className="pp-sheet-actions">
            {armed ? (
              <>
                <span className="pp-row-label">{copy.parent.photos.sure}</span>
                <button type="button" className="pp-text-button" onClick={() => setArmed(false)}>
                  {copy.parent.cancel}
                </button>
                <button
                  type="button"
                  className="pp-button pp-button-bad"
                  onClick={() => remove(open)}
                >
                  {copy.parent.photos.delete}
                </button>
              </>
            ) : (
              <button type="button" className="pp-button" onClick={() => setArmed(true)}>
                {copy.parent.photos.delete}
              </button>
            )}
          </div>
        </Sheet>
      ) : null}
    </Pane>
  )
}
