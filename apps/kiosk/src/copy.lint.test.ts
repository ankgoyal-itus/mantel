import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Every word on a screen comes from copy.ts.
 *
 * Parsed, not grepped: the TypeScript compiler finds the text between JSX
 * tags, string literals written straight into JSX, and the attributes a
 * person reads or hears (aria-label, title, placeholder, alt). Numbers,
 * punctuation and glyphs are not words and are allowed.
 */

const ROOT = fileURLToPath(new URL('.', import.meta.url))
const SPOKEN = new Set(['aria-label', 'title', 'placeholder', 'alt'])
const WORD = /[A-Za-z]{2,}/

function files(folder: string): string[] {
  return readdirSync(folder).flatMap((name) => {
    const path = join(folder, name)
    if (statSync(path).isDirectory()) {
      return files(path)
    }
    return path.endsWith('.tsx') && !path.includes('.test.') ? [path] : []
  })
}

/** Whether a node sits in a JSX child expression rather than an attribute,
    and is not a function's argument (an id, a slot, a date format). */
function insideJsxChild(node: ts.Node): boolean {
  for (let at: ts.Node | undefined = node.parent; at; at = at.parent) {
    if (ts.isCallExpression(at) || ts.isElementAccessExpression(at) || ts.isBinaryExpression(at)) {
      if (ts.isBinaryExpression(at) && at.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken) {
        continue
      }
      return false
    }
    if (ts.isJsxAttribute(at)) {
      return false
    }
    if (ts.isJsxExpression(at)) {
      return ts.isJsxElement(at.parent) || ts.isJsxFragment(at.parent)
    }
  }
  return false
}

function literals(path: string): string[] {
  const source = ts.createSourceFile(path, readFileSync(path, 'utf-8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found: string[] = []
  const where = (node: ts.Node) => {
    const { line } = source.getLineAndCharacterOfPosition(node.getStart())
    return `${relative(ROOT, path)}:${line + 1}`
  }
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node) && WORD.test(node.text)) {
      found.push(`${where(node)} text "${node.text.trim().slice(0, 40)}"`)
    }
    // A string written anywhere inside a JSX child expression — `{a ?
    // 'School day' : note}` — is a word on the screen too. Inside an
    // attribute it is not (a className, a key), unless the attribute is
    // one of the spoken ones below.
    if (ts.isStringLiteral(node) && WORD.test(node.text) && insideJsxChild(node)) {
      found.push(`${where(node)} string "${node.text.slice(0, 40)}"`)
    }
    if (ts.isJsxAttribute(node) && SPOKEN.has(node.name.getText(source))) {
      const value = node.initializer
      if (value && ts.isStringLiteral(value) && WORD.test(value.text)) {
        found.push(`${where(node)} ${node.name.getText(source)}="${value.text.slice(0, 40)}"`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

describe('the words on the screens', () => {
  it('all come from copy.ts', () => {
    const offenders = files(ROOT).flatMap(literals)
    expect(offenders).toEqual([])
  })
})
