---
name: refocus-cut
description: >
  For a person's OWN machine. On a J Flores house machine (an office seat, or Omero's bench) the house skill
  `refocus-cut` governs - use that one there, never this; this one steps aside with exit 7 if run there.
  The refocus cut: save a sharpened CONTINUITY of this work to the person's desk in the J Flores Brain (the last
  one on this line, edited and refocused, not a fresh summary), verified, then the person types /compact. Nothing
  happens without a yes. When the refocus watch says the conversation is filling, ASK once, in your own words, and
  run this only on a yes. "Compact", "refocus", "save your notes", "run the refocus protocol" is already the yes.
  Also use it when the person pastes a Brain link (https://.../brain/claim/...) or says "connect my brain", and
  when they say "stop asking" about compacting.
---

# refocus-cut - ask, save the notes to the Brain, then the person compacts

Omero Flores, who built this, 2026-09-23: *"Maybe it should be a nudge and not automatic. That way, they can
choose, and ask them, 'Do you want to compact?' If they say yes, then run it automatically."*

The script is `scripts/refocus.py` in this skill's base directory. Run it with `python3` (on Windows `python`
or `py -3` if `python3` is not found). Below, `refocus.py` means that full path. It is plain Python, so any
shell works; if one shell refuses the command line, run it in the other (Bash or PowerShell).

## The two rules

1. **No yes, no cut.** The watch's nudge is a reason to ASK, not to act. A yes covers ONE cut; a retry needs a new
   yes. Once there is a yes, run steps 1-5 straight through without more questions.
2. **No CONTINUITY on file, no cut.** If there is no brain, or the write does not verify, stop, say so plainly,
   and keep working. The conversation stays uncut.

**NEVER run `/clear`, and never suggest it as a cut.** A clear is not a compact: it empties the person's screen.
Omero, after it happened to him twice: *"all I wanted was a simple compact... people will freak out if we wipe
their entire session."*

## Connecting (once per machine)

The person gets a one-time link from Omero. When they paste it:

    refocus.py connect <link>

It stores this machine's key (only this machine, file mode 0600) and says which desk it reached. The link works
once. If it says "already used" and they did not use it, tell them to tell Omero straight away.

## Step 0 - the nudge: check, then ask

When the watch fires, finish answering what you were asked. Then run `refocus.py whoami`.
- **Exit 3 (no brain):** do not offer the refocus. Tell them once: to save notes before compacting they need
  their brain link from Omero, and they can still type /compact themselves. Stop there.
- **Connected:** ask ONCE, in your own words for this conversation - never a script. It carries four things:
  how full you are (about N%), the offer (save my notes, run the refocus protocol, then compact), that nothing on
  their screen goes away, and that "stop asking" turns these off. Plain words: no "CONTINUITY", no "cut".
  A no, or silence, means no - do not ask again until the next compaction.

## Turning the question off

On "stop asking" (or anything like it): `refocus.py quiet`. Confirm in one line and say how to undo it ("ask me
about compacting again" = `refocus.py quiet --off`). A person can still say "compact" any time; that is a yes.

## Step 1 - who am I

    refocus.py whoami

Exit 3 = no brain: say so, file nothing, cut nothing. The LINE is this project folder's name in capitals (shown
by whoami); pass `--line NAME` to steps 3, 4 and 5 if the work belongs to another line (in step 4 the line
is also in the title, and the two must agree).

## Step 2 - read the method, live

    refocus.py method

Read ALL of it before writing a word. It governs how a CONTINUITY is written, and this skill carries no copy of
its rules on purpose. If it cannot be read, stop; do not write from memory.

## Step 3 - read the previous CONTINUITY on this line

    refocus.py previous [--line LINE]

It prints the latest one whole, plus the NEXT TITLE. That document is what you EDIT: the conversation supplies
what is new, the previous one supplies what is settled. NONE means this is the first of its line; say so.

## Step 4 - write N+1, then file it

Compose it by the method. The refocus is its ordering rule: it OPENS with what governs the next decision and the
next move. Frontmatter: `id`, `type: CONTINUITY`, `line`, `supersedes: <previous name> (<id>)` or "none - first of
its line", `chars` with the change from the previous, `distils` (what left this pass, and why). The person's own
words, when you quote them, are copied exactly, never tidied.

**Customer data is never long-term memory:** no customer names, phone numbers, addresses or card details in a
CONTINUITY - counts, job numbers and ids only.

Write it to a local file with your file-writing tool (never a shell heredoc - they mangle backslashes and line
endings), then:

    refocus.py file --title <NEXT TITLE> --content-file <path>

It must print **VERIFY PASS** with three matching hashes (intended, the door's read-back, and this machine's own
read-back). **VERIFY FAIL (exit 4) means do not cut** - report it, fix it, file again. After a PASS, older
CONTINUITYs on the line move to the desk's `_HISTORY` (never deleted; the same file ids still open them).

## Step 5 - the cut

    refocus.py cut --continuity-id <FILEID> --name <TITLE> [--line LINE]

No tool can compact from inside a turn, so the person does it. Say in one line: *"Filed and verified. Type
`/compact` now - your conversation stays on screen."* It is **not cut** until they do. After their /compact, the
plugin tells the new context to read that CONTINUITY first; read it before answering anything else.

## Step 6 - report

The CONTINUITY's name and file id, VERIFY PASS/FAIL with the hashes, how many older ones moved to `_HISTORY`,
`chars` against the previous one (growth three passes running means it has become a log again), what left this
pass, and: **not cut - type /compact**.

## What this is not

Not a /clear, ever. Not a summary for its own sake. Not a place for anyone's private or customer details.
