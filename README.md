# J Flores Claude Code plugins

## refocus

The refocus cut for your own Claude Code. When a conversation gets full (40% of the model's window), Claude
asks you once, in its own words, whether to save its notes and compact. On a yes it writes a sharpened
CONTINUITY of the work to **your desk in the J Flores Brain**, verifies it byte for byte, and then **you** type
`/compact`. Nothing on your screen is deleted, and it never runs `/clear`. Say "stop asking" and it stops.

**Setup (once):**
1. Install: `/plugin install refocus --marketplace <this repo>`, or it arrives with the org's managed settings.
2. Omero sends you a one-time link. Paste it into Claude Code and say "connect my brain".

**It needs Python 3** (3.8 or newer). Without it the plugin says so once a day and does nothing else.

Your machine never holds a Brain password. It holds one key for your desk only, fetched once from that link and
stored in `~/.claude/refocus/door.json` (file mode 0600). Each note is written through the Brain door on the J
Flores server, which lets your key write only to your own desk.

**On Windows, the surest setup is one line in PowerShell.** Open the page your link opens and copy its line
(`irm https://.../brain/setup/... | iex`). It finds Claude Code (the desktop app keeps it off PATH), installs the plugins,
connects, and checks for Python. It is safe to run again.

**Share (1.4.0).** When your Claude Code runs into something with the J Flores setup or work, say "send this to Omero"
(or "share this"). It goes to your help room in the J Flores Office, where Monday is called and Omero reads it, and
the answer comes back into your Claude Code on your next message. Anything that needs Omero's permission or access (the
company's saved logins, the server, a key) goes to his phone as **Approve / Decline**, and his answer comes back the same way. Passwords, keys, links and customers' contact
details are never sent.

Since 1.1.0 every note names its side (`work`), because once your steward's private side exists, the door refuses a
note that does not say which side it is on.


## password-manager

Save a password, API key or login into the J Flores secret store without typing it into a terminal or a chat.
Ask Claude to "save a key" (or paste nothing and say what it is for): it makes a one-time link, you open it and paste
each value into its own box. Keys are saved under your own name (`marc-...`), so nobody can overwrite a key the
house already uses. To have an agent or tool use a key, tell Omero or Monday.

## steward

Meet your **Faithful Steward**: a teammate who works with you, and only you. Your steward learns how you work,
keeps your day in order (email, calendar, filing), helps with whatever you're building, and grows into more as the
two of you work together. The name comes from Luke 12:42-44: the steward who first kept the household, and was then
trusted with everything.

**You start it.** Omero talks with you first. When you're ready, type `/steward:start` in a fresh session you can
keep. It welcomes you, then you talk (about 30 to 45 minutes, mostly stories about your work). Titus, the teammate
who forms new teammates in this house, puts your steward together from what you said; you read the draft, correct
it, choose your steward's name, and nothing goes live without your yes. From then on your Claude Code wakes as your
steward in every new session.

**Two sides.** What you share about yourself stays on a private side: no person at the company reads it, Omero
included. What your steward learns about the work is shared, so everyone's builds get better. Your words in the
interview are recorded by the plugin's own code, exactly as you type them, on your private side.

**Setup (once):**
1. Install: `/plugin marketplace add Omerogit/jflores-claude-plugins`, then `/plugin install steward@jflores` (and
   `refocus@jflores` beside it).
2. Omero sends you a one-time link. Paste it into Claude Code and say "connect my brain" (one link connects both
   plugins).
3. Type `/steward:start` when you're ready.

It needs Python 3 (3.8 or newer), like refocus. On a J Flores house machine (an office seat, Omero's bench) it steps
aside and does nothing.
