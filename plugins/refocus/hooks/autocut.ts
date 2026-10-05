// refocus-autocut - the last step of the refocus cut on a desk (2026-10-05, Omero: "go ahead and build it").
//
// refocus.py `cut` (or `finish`) files the CONTINUITY byte-verified, points the door, and ARMS the cut by
// writing ~/.claude/compaction/autocut/<session id>.json. When this session's turn ends, this module sees
// the arming, uses it once, and compacts: $.session.compact() is the same call /compact makes, so the
// conversation stays on screen. It never clears: 1.1 used clear_session and wiped Omero's session twice
// on 2026-09-23.
//
// Fails closed: no arming for THIS session id, an arming older than ARM_TTL, or one already used -> nothing.
// A cut that does not land says so in a toast and in done.json, and the person can still type /compact.

// The refocus plugin's copy of refocus-autocut (refocus 1.7.0, 2026-10-05). The same module runs on Omero's bench
// from ~/.claude/mods/refocus-autocut with SUB = "compaction/autocut"; a person's desk arms ~/.claude/refocus/autocut,
// so the two can never act on the same arming.
const SUB = "refocus/autocut"
const ARM_TTL_S = 30 * 60

async function dir($: any): Promise<string | undefined> {
  const home = (await $.env.get("USERPROFILE")) || (await $.env.get("HOME"))
  if (!home) return undefined
  return home.replace(/\\/g, "/") + "/.claude/" + SUB
}

// This session's id: the engine's own answer, else the variable Claude Code gives the session's tools
// (the same one refocus.py reads to arm the cut).
async function sessionId($: any): Promise<string | undefined> {
  try {
    const id = await $.session.id()
    if (typeof id === "string" && id) return id
  } catch { /* fall through */ }
  return (await $.env.get("CLAUDE_CODE_SESSION_ID")) || undefined
}

async function readJson($: any, path: string): Promise<any> {
  try {
    if (!(await $.fs.exists(path))) return undefined
    const r = await $.fs.read(path)
    return JSON.parse(typeof r === "string" ? r : r.text)
  } catch {
    return undefined
  }
}

export function register(on: any) {
  // Say we are loaded, for this session, so refocus.py can tell the person the cut is automatic.
  on("session.start", async ($: any, e: any, next: any) => {
    const r = await next(e)
    try {
      const d = await dir($)
      const sid = await sessionId($)
      if (d && sid) {
        await $.fs.write(`${d}/loaded-${sid}.json`,
          JSON.stringify({ session_id: sid, at: Math.floor((await $.clock.now()) / 1000), version: "0.2.0" }))
      }
    } catch { /* a missing heartbeat only means refocus.py falls back to "type /compact" */ }
    return r
  })

  on("turn.complete", async ($: any, e: any, next: any) => {
    const r = await next(e)
    if (e.agentId) return r                 // a subagent's turn, never the conversation's
    try {
      const d = await dir($)
      const sid = await sessionId($)
      if (!d || !sid) return r
      const arm = await readJson($, `${d}/${sid}.json`)
      if (!arm || arm.session_id !== sid) return r
      const now = Math.floor((await $.clock.now()) / 1000)
      const done = await readJson($, `${d}/${sid}.done.json`)
      if (done && done.epoch >= arm.epoch) return r          // used: a yes covers ONE cut
      if (now - arm.epoch > ARM_TTL_S || arm.epoch - now > 60) return r   // stale (or future) arming: leave it to the person
      // Mark it used BEFORE compacting, so a retry or a reload can never cut twice.
      const rec: any = { session_id: sid, epoch: arm.epoch, name: arm.name, id: arm.id, started: now }
      await $.fs.write(`${d}/${sid}.done.json`, JSON.stringify(rec))
      const instructions =
        `Put ${arm.name} (Brain file ${arm.id}) first: it is the work, carried and honed. ` +
        `Then summarize the conversation as usual. Never drop a fact that is not in it.`
      // 0.2.0: try the direct compact once; if the engine refuses it for any reason, run /compact itself, as if
      // the person typed it ($.command.run), held by the engine until the session is idle.
      // Why: the desktop app runs every conversation as an SDK session, where $.session.compact is refused
      // ("not available in a headless (-p / SDK) session yet: compaction here runs inside a turn (a /compact
      // prompt)"). The first live cut, CONTINUITY-AHRT-2026-10-05-01 on 2026-10-05, hit exactly this.
      $.clock.after(1500, async () => {
        const finish = async (result: string, toast: string) => {
          rec.result = result
          rec.finished = Math.floor((await $.clock.now()) / 1000)
          await $.fs.write(`${d}/${sid}.done.json`, JSON.stringify(rec))
          $.ui.toast(toast)
        }
        let why = ""
        try {
          const res = await $.session.compact({ instructions })
          if (!(res && res.skip)) {
            rec.tokens_before = res && res.tokensBefore
            rec.tokens_after = res && res.tokensAfter
            return finish("compacted", `Refocus cut: compacted onto ${arm.name}`)
          }
          why = `skipped: ${res.skip}`
        } catch (err: any) {
          why = String(err && err.message || err).slice(0, 200)
        }
        rec.direct = why
        try {
          // A mod may not send a /command as a prompt; $.command.run runs it as if the person typed it,
          // queued until the session is idle.
          await $.command.run({ command: "compact", args: instructions })
          return finish("submitted /compact", `Refocus cut: compacting onto ${arm.name}`)
        } catch (err2: any) {
          return finish(`failed: ${why} | /compact prompt: ${String(err2 && err2.message || err2).slice(0, 200)}`,
            "Refocus cut NOT done - the notes are saved. Type /compact.")
        }
      })
    } catch { /* never break the turn's answer */ }
    return r
  })
}
