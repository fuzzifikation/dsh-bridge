/**
 * Tripwires for the uninstall sizing. The number only ever feeds a human
 * sentence, but it is the number a user weighs a destructive confirmation
 * against - so a walk that skips nested trees or dies on a missing directory
 * misreports what an uninstall is about to delete.
 */
import { it, expect, describe } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { directorySize, formatBytes, deletableWithin } from '../out/bridge/disk.js'

describe('directorySize', () => {
  it('sums files through nested trees', () => {
    const root = mkdtempSync(path.join(tmpdir(), 'dsh-disk-'))
    try {
      writeFileSync(path.join(root, 'a.txt'), 'x'.repeat(10))
      mkdirSync(path.join(root, 'deep', 'deeper'), { recursive: true })
      writeFileSync(path.join(root, 'deep', 'b.txt'), 'y'.repeat(20))
      writeFileSync(path.join(root, 'deep', 'deeper', 'c.txt'), 'z'.repeat(5))
      expect(directorySize(root)).toBe(35)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('answers zero for a missing directory instead of throwing', () => {
    expect(directorySize(path.join(tmpdir(), 'dsh-disk-does-not-exist'))).toBe(0)
  })
})

describe('formatBytes', () => {
  it('spells sizes the way the confirmation says them', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(1536 * 1024)).toBe('1.5 MB')
    expect(formatBytes(3 * 1024 ** 3)).toBe('3.0 GB')
  })
})

describe('deletableWithin', () => {
  it('permits only real directories strictly inside the boundary', () => {
    const base = mkdtempSync(path.join(tmpdir(), 'dsh-del-'))
    try {
      const inner = mkdirSync(path.join(base, 'dsh-home'), { recursive: true }) && path.join(base, 'dsh-home')
      expect(deletableWithin(path.join(base, 'dsh-home'), base)).toBe(true)
      mkdirSync(path.join(base, 'a', 'b'), { recursive: true })
      expect(deletableWithin(path.join(base, 'a', 'b'), base)).toBe(true)
      // never the boundary itself, never a file, never a missing path,
      // never anything that resolves outside
      expect(deletableWithin(base, base)).toBe(false)
      writeFileSync(path.join(base, 'file.txt'), 'x')
      expect(deletableWithin(path.join(base, 'file.txt'), base)).toBe(false)
      expect(deletableWithin(path.join(base, 'gone'), base)).toBe(false)
      expect(deletableWithin(path.dirname(base), base)).toBe(false)
      expect(deletableWithin(path.join(base, '..', '..'), base)).toBe(false)
    } finally {
      rmSync(base, { recursive: true, force: true })
    }
  })
})
