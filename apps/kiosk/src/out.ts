/**
 * Lunch out and Dinner out: meals that are a place, not a dish.
 *
 * The API reserves both ids and carries the place in the meal's note. Every
 * screen that shows a meal asks here whether it is one, so an out meal reads
 * the same everywhere: "Out · Taqueria Luna", with the storefront.
 */

import { copy } from './copy'

export const DINNER_OUT = 'dinner_out'
export const LUNCH_OUT = 'lunch_out'

export function isOut(id: string | null | undefined): boolean {
  return id === DINNER_OUT || id === LUNCH_OUT
}

/** "Out · Taqueria Luna" for an out meal; the dish's own name for anything else. */
export function mealName(meal: { id?: string | null; name: string; note?: string | null }): string {
  return isOut(meal.id) ? copy.out.label(meal.note) : meal.name
}

/** The place, trimmed and whitespace-collapsed, or null. At most 40. */
export function cleanPlace(text: string): string | null {
  const place = text.split(/\s+/).filter(Boolean).join(' ')
  return place ? place.slice(0, 40) : null
}
