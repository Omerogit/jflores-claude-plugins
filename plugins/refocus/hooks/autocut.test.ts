import { test, expect, mock } from 'claude-code/testing'

const D = 'C:/Users/t/.claude/refocus/autocut'
const k = (p: string) => p.split(String.fromCharCode(92)).join('/')   // the engine hands hooks the native (backslash) path

function world(on: any, files: Record<string, string>, compactFails = 0) {
  const calls: any[] = []
  const submits: any[] = []
  let fails = compactFails
  mock.env(on, { USERPROFILE: 'C:\\Users\\t', CLAUDE_CODE_SESSION_ID: 'S-env' })
  const clock = mock.clock(on, { now: 1_000_000_000_000 })
  on('fs.exists', ($: any, e: any) => ({ value: k(e.path) in files }))
  on('fs.read', ($: any, e: any) => {
    if (!(k(e.path) in files)) throw new Error('missing')
    return { value: files[k(e.path)] }
  })
  on('fs.write', ($: any, e: any) => { files[k(e.path)] = e.text; return { value: undefined } })
  on('session.compact', ($: any, e: any) => {
    calls.push(e)
    if (fails > 0) { fails--; throw new Error('a turn is running') }
    return { messages: [{ role: 'user', text: 'summary', toolUses: [] }], tokensBefore: 400000, tokensAfter: 140000 }
  })
  on('ui.toast', () => ({ value: undefined }))
  on('turn.complete', ($: any, e: any) => ({ text: e.answer }))
  on('command.run', ($: any, e: any) => { submits.push(e); return { text: 'compacted' } })
  on('session.start', ($: any, e: any) => ({ cwd: e.cwd }))
  return { calls, clock, files, submits }
}

// what the plugin will take as this session's id: the engine's, else the variable
async function sid($: any): Promise<string> {
  try { const id = await $.session.id(); if (typeof id === 'string' && id) return id } catch {}
  return 'S-env'
}

const arm = (sid: string, epoch: number) =>
  JSON.stringify({ session_id: sid, epoch, name: 'CONTINUITY-X-2026-10-05-01', id: 'FILEID', line: 'X' })

const turn = { answer: 'ok', durationMs: 5, isAborted: false, turnId: 't1', reason: 'answer' } as any

test('armed for this session: compacts once, after the turn, with the CONTINUITY first', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, { [`${D}/${S1}.json`]: arm(S1, 1_000_000_000 - 60) })
  await $.turn.complete(turn)
  expect(w.calls.length).toBe(0)                 // never inside the turn
  await w.clock.advance(2000)
  expect(w.calls.length).toBe(1)
  expect(w.calls[0].instructions).toContain('CONTINUITY-X-2026-10-05-01')
  expect(JSON.parse(w.files[`${D}/${S1}.done.json`]).result).toBe('compacted')
  await $.turn.complete(turn)                    // a yes covers ONE cut
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(1)
})

test('MUST-FAIL: an arming for another session never compacts this one', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, { [`${D}/${S2}.json`]: arm(S2, 1_000_000_000 - 60) })
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(0)
})

test('MUST-FAIL: a file named for this session but holding another id is refused', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, { [`${D}/${S1}.json`]: arm(S2, 1_000_000_000 - 60) })
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(0)
})

test('MUST-FAIL: a stale arming (over 30 minutes) is left to the person', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, { [`${D}/${S1}.json`]: arm(S1, 1_000_000_000 - 31 * 60) })
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(0)
})

test('MUST-FAIL: no arming, no cut', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, {})
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(0)
})

test('a refused direct compact falls back to the /compact prompt, once', async ($, on) => {
  const S1 = await sid($)
  const w = world(on, { [`${D}/${S1}.json`]: arm(S1, 1_000_000_000 - 60) }, 1)
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(1)
  expect(w.submits.length).toBe(1)
  expect(w.submits[0].command).toBe('compact')
  expect(w.submits[0].args.startsWith('Put CONTINUITY-X-2026-10-05-01')).toBe(true)
  expect(JSON.parse(w.files[`${D}/${S1}.done.json`]).result).toBe('submitted /compact')
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(1)
  expect(w.submits.length).toBe(1)
})

test('session start leaves the heartbeat refocus.py reads', async ($, on) => {
  const S1 = await sid($); const S2 = S1 + '-other'
  const w = world(on, {})
  await $.session.start({ source: 'startup', cwd: 'C:/x' } as any)
  expect(JSON.parse(w.files[`${D}/loaded-${S1}.json`]).session_id).toBe(S1)
})

test('MUST-FAIL: an arming dated in the future is refused', async ($, on) => {
  const S1 = await sid($)
  const w = world(on, { [`${D}/${S1}.json`]: arm(S1, 1_000_000_000 + 600) })
  await $.turn.complete(turn)
  await w.clock.advance(5000)
  expect(w.calls.length).toBe(0)
})

