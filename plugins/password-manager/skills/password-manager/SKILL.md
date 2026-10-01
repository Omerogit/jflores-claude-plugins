---
name: password-manager
description: >
  For a person's OWN machine. On a J Flores house machine (an office seat, or Omero's bench) the house skill
  `password-manager` governs - use that one there, never this; this one steps aside with exit 7 if run there.
  Put a password, API key, token, client ID/secret or any other login into the J Flores secret store without the
  person typing it into a terminal or into this chat: make a one-time link, give it to them, and they paste each
  value into its own box in their browser. Use it whenever someone has a new key or login from a vendor, a key was
  changed or reissued, something needs "saving in the secret manager" or "the password manager", or a new agent
  or tool they are building needs a login - and whenever someone pastes a key into the chat.
---

# password-manager - a one-time link, so a key never passes through a terminal or a chat

Omero Flores, 2026-09-22, on why this exists: *"the copy-paste is so confusing and never lands correctly that it
literally puts the brakes on progress... We have to build something."* And 2026-10-01: *"Make it available to Marc
and everyone on the team."*

The script is `scripts/keys.py` in this skill's base directory. Run it with `python3` (on Windows `python` or
`py -3` if `python3` is not found). Below, `keys.py` means that full path. It uses the Brain key this machine
already has (from the refocus plugin's "connect my brain"). If it says no brain is connected, tell the person to
ask Omero for their Brain link.

## The rules

1. **Never take the value in this chat, and never put it in a command.** Not in a terminal, not in a file, not in
   an environment variable. The value goes from the person's browser straight into the store. If someone pastes a
   key here anyway, say once, plainly, that it is now in this conversation's history and should be changed at the
   vendor, then make the link for the new one.
2. **Keys are saved under the person's own name.** Ask for `hcp-api` and it is saved as `marc-hcp-api` (the door
   adds the name). Nobody can overwrite a key the house's teammates already use. That is on purpose.
3. **Saving a key is not using it.** A teammate or tool reads a key only once Monday connects it. After it lands,
   tell the person to let Omero (or Monday) know which agent or tool should read it.

## Steps

1. **Find out what it is.** Which company or tool, and what the vendor calls each value: "Client ID", "Client
   Secret", "API Key", "Username", "Password". One login with several values is ONE key with several boxes.
2. **Make the link:**

       keys.py request <short-name> --field "<vendor's label>=<json_key>" [--field ...] --note "<what it is for>"

   - `short-name`: lower case, digits and dashes, e.g. `hcp-api`, `marcone-ftp`.
   - each `--field`: the label the person will see (in the vendor's own words), `=`, a lower-case json key such as
     `client_id`, `api_key`, `username`, `password`.
   - `--ttl` minutes, default 30. Use longer only if they will do it later.
3. **Give them the link** (the `KEY LINK` line) with one sentence: open it, paste each value into its box, press
   the button. Opening it does not use it up.
4. **Check it landed:** `keys.py status`. A saved key shows its version, `check=PASS`, and each box's length and a
   short fingerprint - never the value. If the length looks wrong (a 40-character key saved as 3), make a new link.
5. **Say what's next:** it is saved as `<name>`; to have an agent or tool use it, tell Omero or Monday.

## Exit codes

3 no brain connected - install the refocus plugin and use your Brain link first (or the key was turned off) - 5 the door refused, and says why in words - 6 the door did not
answer - 7 a house machine: use the house `password-manager` skill.
