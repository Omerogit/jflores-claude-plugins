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
