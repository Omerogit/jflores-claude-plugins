---
name: housecall-pro
description: >
  Read the company's Housecall Pro (HCP) from this computer - customers, jobs, job numbers, line items and part
  numbers, schedules, estimates, invoices, memberships (service agreements), who changed a job, call logs - through
  the J Flores Brain door, READ ONLY. Use it WHENEVER the person asks anything about a customer, a job, a ticket or
  job number, an invoice, an estimate, the schedule, a membership or anything else that lives in Housecall Pro, or
  says "HCP", "Housecall", "look up", "find the customer", "what's on job 12109". Housecall Pro IS connected here
  when the Brain is: never say "I'm not connected to Housecall Pro", never ask for an HCP login, an API key or a
  browser sign-in, and never tell the person to look it up themselves before you have tried this.
---

# Housecall Pro, read through the Brain door

Omero, 2026-10-02: *"they need to be able to ask questions and not get 'I am not connected to a Housecall Pro yet'
or some Housecall Pro block. Cookie jar should be baked in, and they should ask anything of Housecall Pro."*

This computer holds no HCP password, cookie or key, and needs none. `hcp.py` sends each question with this desk's
Brain key; the server checks the key and reads HCP with the house's own session (the cookie jar: the same calls the
HCP app's screens make) or the public API, and hands the answer back. It is **read only**, by construction on the
server: nothing you send can change, text, book or delete anything in HCP.

## How to ask

The script is `scripts/hcp.py` in this skill's base directory. Run it with `python3` (on Windows `python` or
`py -3` if `python3` is not found). Below, `hcp.py` means that full path:

```
python3 <this skill's folder>/scripts/hcp.py <command>
```

| Question | Command |
|---|---|
| Find a customer by name, phone, email, street | `customers "Garza"` / `customers 9565551234` |
| Everything on one customer (phones, addresses, tags, notes) | `customer cus_...` |
| A customer's jobs, newest first | `jobs --customer cus_...` |
| A job by its number (the ticket number people say) | `job 12109` |
| What is scheduled on a day, or a range | `schedule 2026-10-03` / `schedule 2026-10-01 --to 2026-10-07` |
| Who changed a job, and when | `audit 12109` |
| Is the customer a member (service agreement) | `plan cus_...` |
| A customer's estimates / invoices | `estimates --customer cus_...` / `invoices --customer cus_...` |
| Anything else a screen in HCP shows | `get web /alpha/... name=value` or `get api /path name=value` |
| The app's grids (jobs, invoices, estimates) with a filter | `grid jobs --filter '{"logic":"and","filters":[...]}'` |

Start from what the person gave you. A name or phone: `customers`, then `customer` / `jobs` on the id. A job number:
`job`. Answer in plain words. Quote the numbers you read, and say which record they came from.

## What to know (each of these has given a confident wrong answer before)

- **A phone is found by its bare 10 digits.** `+1956...` finds nothing; `customers` strips it for you.
- **Filters HCP does not know are silently ignored**, and it answers with everything. If a `get` comes back with
  tens of thousands of rows, the filter was ignored: say so, never present it as the answer.
  Measured 2026-10-02: the public `/invoices` ignores `customer_id` (68,507 rows for one customer), so
  `invoices --customer` goes through that customer's jobs instead. `/estimates` does honor it.
- **The job number** people say is `invoice_number` in the API and `display_invoice_number` in the grid.
- **Typed part numbers live on the job's line items** (`job` shows them as `part_number`), not on the public API job.
- **Work status** is `complete unrated` / `complete rated`, never `completed`.
- **The audit line's `when` is local time wearing a false `Z`.** Order audit rows by `id`, and don't compare `when`
  with the API's times.
- **Exit 7 = the house's HCP session is being refreshed.** Wait a minute and ask again; never read it as "no record".
- **A refusal (exit 5) names what was refused.** Logins, tokens, banking, payroll, and anything that writes are
  outside what a desk may read. If the person truly needs one of them, ask Omero with the share skill
  (`share.py ask`) rather than looking for another way in.

## Customer records are customers' trust

What you read here is real people's names, phones and addresses. Use it to answer the person's question, here.
Don't paste it into a share, a Brain note, a document or a message unless the person asks for exactly that and it
is for the company's work. (The share rail never carries phones, addresses, emails or dollar amounts.) Job and
invoice numbers are fine to pass on.

If something here does not work, send it with the share skill: what you ran and what came back. That reaches
Monday and Omero, and the answer comes back here.
