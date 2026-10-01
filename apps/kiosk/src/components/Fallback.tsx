import { Component, type ErrorInfo, type ReactNode } from 'react'
import { copy } from '../copy'

/**
 * One broken card is a broken card, not a blank screen.
 *
 * The API has had this rule since v1: a bad YAML file never crashes it, it
 * serves the last good version and logs the path and the error. The kiosk had
 * no such rule, and it cost exactly what you would expect — `types.ts` said
 * `diet.no_non_veg_dates` and the API had never had a field by that name, so
 * one `undefined.length` in one card unmounted the whole parent screen. What
 * a parent saw was nothing at all: no message, no tabs, no way back.
 *
 * React only offers this as a class, which is why this is the one class
 * component in the app.
 *
 * Deliberately not on the kid screens. A child seeing "Something broke here"
 * is worse than a child seeing a screen that came back on the next poll, and
 * those screens are rebuilt from the API every few minutes anyway. This is for
 * parent mode, where a person is reading a form and needs the rest of it.
 */
type Props = { children: ReactNode; what: string }
type State = { failed: boolean }

export default class Fallback extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // The console is the only log the kiosk has, and /diag is where somebody
    // would go looking. Naming the section is the point: "Settings" is the
    // difference between a bug report and a shrug.
    console.error(`[mantel] ${this.props.what} failed to render`, error, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.failed) {
      return this.props.children
    }
    return (
      <section className="pp-card">
        <h2 className="pp-card-title">{this.props.what}</h2>
        <p className="pp-muted">{copy.shell.partFailed}</p>
      </section>
    )
  }
}
