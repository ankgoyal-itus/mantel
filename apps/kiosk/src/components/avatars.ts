/**
 * The bundled animals, as the avatar picker offers them.
 *
 * The same set as AVATARS in mantel_api/models.py and the drawings in
 * src/avatars/: family.yaml is validated against the API's copy, so a name
 * here that is not there would be refused on save rather than drawn blank.
 */
export const AVATARS = [
  'bear',
  'cat',
  'deer',
  'dog',
  'elephant',
  'fox',
  'frog',
  'giraffe',
  'hedgehog',
  'koala',
  'lion',
  'monkey',
  'octopus',
  'owl',
  'panda',
  'parrot',
  'penguin',
  'rabbit',
  'seal',
  'tiger',
  'turtle',
  'whale',
  'wolf',
  'zebra',
] as const
