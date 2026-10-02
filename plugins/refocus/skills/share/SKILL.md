---
name: share
description: >
  Send what this Claude Code ran into to the J Flores house (Monday and Omero), and bring their answer back here.
  Use it when the person says "send this to Omero", "send it to Monday", "share this", "ask the house", "ask
  Omero"; when they ask "did Omero (or Monday) answer?"; and when you are stuck on this computer's J Flores setup
  or work (a plugin, the Brain, a J Flores tool or rail, a command that is blocked, a tool that is missing) and the
  person says yes to sending it. Not for a J Flores house machine (an office seat or Omero's bench).
---

# share - ask the J Flores house, and get the answer back here

Omero Flores, 2026-10-02: *"when he comes across things in his Claude Code, he can share them, and we can point him
in the right direction."* Before this it was copy and paste over Telegram. Now what you send lands in the person's
help room in the J Flores Office; Monday (the company's chief of staff, a teammate of the house) is called on it,
Omero reads it, and the answer comes back to this Claude Code.

The script is `scripts/share.py` in this skill's base directory. Run it with `python3` (on Windows `python` or
`py -3` if `python3` is not found). Below, `share.py` means that full path. It uses the key `refocus.py connect`
stored; with no brain connected it says so (exit 3) and sends nothing.

## When you are stuck, offer it once

If you hit something about this computer's J Flores setup or work that you cannot get past - a refusal, a missing
command, an error you cannot explain, a step the person's instructions assumed would work - say what happened in
plain words, and offer once: "Want me to send this to Omero and Monday? They can point us the right way." Do not
send without a yes, unless the person already asked you to send it. Never keep retrying around a block instead.

## What to send

Write it so someone who cannot see this screen can help on the first read:

1. **What the person was trying to do**, in a line.
2. **What was run or asked**, exactly (the command, or the message they pasted).
3. **What came back**, exactly - copy the error or refusal word for word. Do not summarize an error.
4. **What you already tried**, and what each try said.
5. **This computer**: Windows or Mac, and whether this is the Claude desktop app or a terminal.

**Never put in a share:** a password, API key, token or Brain link; a customer's phone number, address, email or
any dollar amount. Job and invoice numbers are fine. If the thing that broke involves one of those, describe it
("the customer's address") instead of copying it.

Show the person what you are about to send in a few lines (they may want to add something), then:

    share.py send --title "<a few words>" --file <a file holding the text>

Write the text to a file first (a temp file is fine) so nothing is lost to quoting. It prints **SENT ... VERIFY
PASS** when the house has it word for word. Tell the person it is sent, and that the answer will show up here.

## When the answer comes back

The refocus watch checks for answers while a share is open. When one has arrived, it hands it to you at the start
of the person's next message. **Show it to the person first, in full, before anything else** - it is written to
them. Then help them do what it says. If the person asks whether anyone answered:

    share.py replies

`share.py thread` shows the last messages both ways, if they want to see what was sent.

If the answer is a fix you can carry out here, offer to do it. If it needs something only the person can do (a
command they must run themselves, a setting only they can change), say so plainly and walk them through it.
