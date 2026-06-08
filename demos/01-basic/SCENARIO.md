# Demo 01 - Basic DSAR deadline tracking

A small company has logged four data-subject requests under GDPR Chapter III.
This demo runs the `dsar` subcommand to compute statutory deadlines (one month
per Art. 12(3), extendable to three months) and flag anything overdue or due soon.

## Input

`dsar_requests.json` contains four requests:

- `REQ-001` - an **access** request received 2026-04-10, never fulfilled. With
  today pinned to 2026-06-08 it is well past the 30-day window -> **overdue**.
- `REQ-002` - an **erasure** request received 2026-05-20, marked `extended`
  (complex), so the deadline is 60 days out -> still **open**.
- `REQ-003` - a **portability** request received 2026-05-25, due 2026-06-24,
  inside the 7-day warning window relative to a later "today" -> **due_soon**
  / **open** depending on date.
- `REQ-004` - a **rectification** request received 2026-04-01 and fulfilled
  2026-04-15 -> **closed_ontime**.

## Run it

```sh
python -m gdprkit dsar demos/01-basic/dsar_requests.json --today 2026-06-08
python -m gdprkit --format json dsar demos/01-basic/dsar_requests.json --today 2026-06-08
```

Because `REQ-001` is overdue, the tool prints the breakdown and **exits non-zero**
(1), which is convenient for CI / compliance gates.

Try the other engines too:

```sh
python -m gdprkit ropa demos/01-basic/ropa.json
python -m gdprkit cookies demos/01-basic/cookies.json
```
