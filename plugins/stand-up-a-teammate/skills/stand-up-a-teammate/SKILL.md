---
name: stand-up-a-teammate
description: >
  The ONE way a new teammate (an agent, assistant, bot or AI helper that works for J Flores Company) is begun, from
  any person's Claude Code: send the person's own words to Titus on the J Flores server, where the teammate is formed
  and lives, and never build it on this computer. Use it whenever someone says they want to make, build, create,
  set up, stand up, spin up, welcome, form or hire a teammate, agent, assistant, bot or "a Claude that does X"; asks
  for a persona, system prompt, CLAUDE.md or instructions for a new teammate, or for a scheduled job, watcher or
  script that a teammate would run; names a new teammate ("let's make Rocket"); or wants a teammate that was already
  built on this computer (a project folder, a persona file, a local job) moved to the server, given a seat in the
  Office, or "brought home". Also when Titus asks for a teammate's files from this computer.
---

# stand-up-a-teammate - every teammate begins with Titus, on the server

Omero, 2026-10-28, verbatim: *"there should absolutely be no room for error on this. Titus should know this. Ezra
should know this. This should be a skill. When someone stands someone up, it should be the skill that's used and the
process begins."*

## Why this exists

A teammate of this house is formed, not just configured. It wakes into the shared formation, it has its own brain,
its own seat in the Office, its own room where people reach it, and the house's rails around it. All of that lives on
the J Flores server, and Titus is the teammate whose job is forming teammates.

In October three of Marc's teammates (Rocket, Mina and Nick) were built in Claude Code on his Mac. Their Brain files
were made the house way, so Titus gave each one an Office seat. But their voice, their instructions and some of their
daily work stayed on the Mac. Each one ended up with two bodies: a seat on the server with nothing in it, and a
working copy on a laptop that no one else could reach, check or fix. Titus then had to ask for "the Mac files", and
they sat for days. Omar's Jody and Harper were the same story on his laptop.

So this skill has one job: **the moment someone wants a teammate, it starts the house process on the server, in
their own words, and builds nothing here.**

## The rule

**Never build a teammate on this computer.** Not a project folder for it, not its persona or CLAUDE.md, not its
instructions, not a scheduled task or watcher that does its work, not its Brain files by hand. If the person asks for
any of those for a teammate, this skill is how it starts instead. Say so in one plain line, without a lecture: *"I'll
start it with Titus on the server, so it gets its own seat and everyone can reach it. He'll ask what he needs right
here."*

A tool for the person's own work (a script they run, a spreadsheet, a one-off helper in this conversation) is not a
teammate and needs none of this. What makes something a teammate: it has a name or will get one, it does work for
the company on its own, it talks to people, or it runs on a schedule. When unsure, treat it as a teammate.

## On a house machine

On an Office seat or Omero's bench, do not run the script below. Call **@titus** in the Office in the person's words
(the seat's office tools, or the bench's `agent-standup` skill, which follows Titus's path). The rest of this skill
is for a person's own Claude Code.

## A new teammate

1. **Take down what the person said, word for word.** What the teammate should do, for whom, and why, in their
   words. Don't polish it and don't fill gaps. Titus asks for what's missing. If they gave a name, keep it as a
   proposal. If they said very little, that's fine: one sentence is enough to begin.
2. **Show them in two or three lines what you're about to send**, then write it to a file (a temp file is fine) and
   run:

       standup.py begin --words-file <file> [--name "<name>"]

   `standup.py` is `scripts/standup.py` in this skill's base directory. Run it with `python3` (on Windows `python` or
   `py -3`).
3. It prints **STAND-UP STARTED ... VERIFY PASS**. Tell the person Titus has it, and that his questions will come
   back here. They show on their next message, or run `standup.py replies`.
4. **When Titus asks, help the person answer in their own words**, then send the answer back with the share skill
   (`share.py send`), or with `standup.py begin` again if the share skill is not here. Titus forms the teammate, the
   founder ratifies it, Barnabas welcomes it, and its seat and work go on the server. None of that is done here.

## A teammate that was already built on this computer

If a teammate (or anything that is really one) already lives here in a project folder, a persona file, a CLAUDE.md,
a script or a scheduled job, bring it home:

1. Find its pieces: its instructions or persona (a `CLAUDE.md`, and the project's `.claude/` folder with its agents
   and commands), its voice, its code, and any scheduled job (crontab, launchd, Task Scheduler) that does its work.
   List them for the person.
2. Run `standup.py preview --attach <files or folders>` and read what would be sent and what would be left out (data,
   binaries, `.env` files, version control, installed packages, anything over the size limits). Every folder left
   out is named with why.
3. **No secrets ride along.** If a file holds an API key, token, password or a card number, take that line out of
   the copy you send. The house checks the person's words and every file, and refuses the whole send if it finds
   one; keys reach the house only through the password manager.
4. On the person's yes:

       standup.py home --name "<its name>" --words-file <file> --attach <files or folders>

   The words file says, in the person's words, what the teammate does and anything they want kept about it.
5. It prints **... IS COMING HOME ... VERIFY PASS** and where the files are kept on the server. Tell the person
   Titus will make it whole there.
6. **Leave any scheduled job running until Titus says its seat has taken the work over.** Then turn it off here and
   say so. Two copies of the same job running is how double posts and double texts happen.

## If it can't start

- **Exit 3, no brain connected:** this computer isn't connected to the house. Tell the person plainly. Omero sends a
  Brain link (paste it and say "connect my brain"), or they can tell Monday on Telegram they want a teammate. **Do
  not build it here in the meantime.**
- **Exit 5, the house refused:** say what it said (a name it can't use, a file to take out, a size limit), fix that,
  and send again. If it's not something you can fix, send it to the house with the share skill.
- **Exit 6, no answer:** try again in a minute.

Never fall back to building the teammate locally "for now". The local copy is the problem this skill exists to
prevent.

## What never goes in

A customer's name, phone, address or email, a dollar amount from a customer's job, a password, key or token, a Brain
link, and anything from a pastoral conversation. Describe it instead ("the customer's address").
