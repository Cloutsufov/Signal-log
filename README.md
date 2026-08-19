# Signal log

A personal, paper-traded options research journal. It pulls real market data on
a schedule, records a directional call with a confidence number, and scores that
call the next day against **real option prices** — so you find out whether the
thing has an edge instead of guessing.

**Cost: $0/month.** No API keys, no paid tiers, no broker connection, no signup.
Runs entirely on GitHub Actions and one SQLite file in the repo.

---

## What this is not

Read this part twice.

- **It is not a money printer.** Nobody in the room will tell you this has an
  edge, because nobody knows yet — that's the point of the scoring table.
- **It does not place trades.** There is no broker integration and there is
  deliberately no path to add one quickly. See "Why not Robinhood" below.
- **It is not financial advice**, and the calls it logs are hypothetical.
- **Option P&L is marked mid-to-mid**, which is optimistic. Real fills cross the
  spread and pay commission. If the optimistic number is negative, the real one
  is worse.

The single most useful outcome of running this for 30 days is finding out the
hit rate is a coinflip and saving yourself a year. That is a *good* result.

---

## Three pages

| Page | Question it answers |
|---|---|
| `index.html` — **Signals** | What does it say right now, and is the data fresh? |
| `record.html` — **Record** | Should I believe it? Does confidence mean anything? |
| `news.html` — **News** | What's going on, from whom, and how old is it? |

The freshness banner appears on all three, because staleness is never irrelevant.

---

## About confidence

You cannot turn confidence up. Confidence is a **claim the model makes**, not a
dial on the system — raising it without raising accuracy just makes the thing
lie to you more assertively. The version of that request worth building is
measuring whether the claim is worth anything, which is what the Record page now
does.

It buckets every scored call by the confidence it claimed and shows the hit rate
for each bucket, then gives a blunt verdict:

- **"Confidence is informative"** — high-confidence calls beat low-confidence
  ones by 10+ points. The number is carrying signal; weight your attention by it.
- **"Confidence is noise"** — the gap is inside the noise. The number is
  decoration. Ignore it.
- **"Confidence is INVERTED"** — high-confidence calls do *worse*. The model is
  most wrong exactly when it's most sure. This is the dangerous one, it is common,
  and you would never see it without this table.

Below ~20 scored calls it refuses to judge at all and says so.

---

## The eight boxes on the Signals page

Every section carries a numbered marker matching a "How to read this page"
legend at the top, and every context box explains itself in place.

| # | Box | What it answers |
|---|---|---|
| ① | **The call** | The logged hypothesis — direction, confidence, reasoning. Labelled a hypothesis, not a recommendation, because that's what it is. |
| ② | **Already priced in** | The ATM straddle-implied move to expiry and the one-day expected move. A call predicting a move *smaller* than this is predicting nothing. |
| ③ | **What it costs** | Breakeven price, the % move needed to reach it, and the spread as a share of premium. Warns when breakeven needs a bigger move than the market is pricing. |
| ④ | **Volatility context** | Implied vs realized vol, the ratio, and where current IV sits in the recorded range. Flags when options are expensive relative to how much the thing is actually moving. |
| ⑤ | **Agreement** | Whether SPY/QQQ/IWM calls point the same way. They track the same market; disagreement means at least one is noise. |
| ⑥ | **Track record** | Hit rate, average option P&L, current streak — with a note that 3–4 in a row either way is normal at these sample sizes. |
| ⑦ | **Markets** | Price, day change, sparkline and freshness per tracked symbol. |
| ⑧ | **Pipeline health** | Whether the machinery actually ran. |

All of these are computed from data already in the database — no new sources, no
new dependencies, no extra cost.

---

## The three rails

| Rail | Schedule | What it does |
|---|---|---|
| **Crypto** | every 30 min, 24/7 | BTC-USD, ETH-USD spot + 14d daily closes |
| **News** | every 30 min | 25 RSS feeds, primary sources tiered above press |
| **Equities** | weekdays, 8:30am + 4:30pm ET | **parked** — every free keyless source 429s from a cloud IP |

The **display layer** is separate and real-time: crypto prices tick live over
Coinbase's free public WebSocket straight from the browser, and freshness ages
recompute every second. That layer is display-only — it is never recorded,
never scored, never fed into a call.

The news rail is **read-only**. Headlines are shown to you and are never fed to
the model. That is a security control, not an oversight — see `fetch_news.py`.

---

## Setup

**→ See [SETUP.md](SETUP.md) for the full phone-only walkthrough.**

Short version — four button presses, no terminal:

1. Put the code in a **public** GitHub repo.
2. **Settings → Actions → General → Workflow permissions** → *Read and write*.
3. **Actions → bootstrap (run this first) → Run workflow.** This probes every
   source, prunes dead feeds, pulls the first real data, and builds the pages.
4. **Settings → Pages** → branch `main`, folder `/docs`.

You never need Python locally. The Actions runner has full internet access and
does all the fetching, scoring and building. Recording a call is a form in the
Actions tab — pick the symbol, paste the JSON, press Run.

---

## The daily loop

The automated half is data and scoring. The judgment half is you, because a
model API call inside Actions would cost money and you asked for free.

1. Actions snapshots the market at 8:30am / 4:30pm ET and writes `PROMPT.md`.
2. Open `PROMPT.md` on your phone, copy it, paste into Claude.
3. Claude returns JSON. **Actions → "record a call" → Run workflow**, pick the
   symbol, paste the JSON.
4. Tomorrow's run scores it automatically. Nothing else to do.

The equivalent from a terminal, if you happen to be at one:

```
python3 scripts/record_call.py --symbol SPY --json '{"direction":"up","confidence":3,
  "rationale":"...","invalidation":"below 548"}'
```

`PROMPT.md` deliberately contains **only numbers** — spot, previous close, recent
closes, the ATM chain with IV and spreads, and the model's own track record. No
headlines. If it can't make a call from the data, it doesn't have a call.

---

## Commands

```
python3 scripts/doctor.py                       # probe every live source, report what works
python3 scripts/doctor.py --prune               # ...and delete the dead feeds
python3 scripts/fetch_market.py --class equity --symbols SPY,QQQ,IWM
python3 scripts/fetch_market.py --class crypto --symbols BTC-USD,ETH-USD
python3 scripts/make_prompt.py --symbol SPY     # writes PROMPT.md
python3 scripts/record_call.py --symbol SPY     # reads JSON from stdin
python3 scripts/score.py                        # score matured calls, print record
python3 scripts/score.py --all                  # rescore everything
python3 scripts/build_site.py                   # rebuild all three pages
python3 tests/test_parsers.py                   # 133 offline tests, no network
```

No `pip install` anywhere. Python 3.9+ standard library only.

---

## How scoring works

Two numbers, always shown together:

1. **Direction correct** — did spot move the way the call said. This is the
   vanity metric. A `flat` call counts as correct if the move stayed inside a
   band of **0.31 sigma of that symbol's own realized daily volatility** —
   about 0.25% on SPY, closer to 1% on BTC. The constant is fixed in `score.py`
   and every scored row records how its band was derived, so the record can be
   audited and the threshold can't be quietly widened later to flatter it.
2. **Option P&L %** — what the specific ATM contract named *at call time*
   actually did. The contract symbol, its mid, and its bid/ask spread are locked
   in when the call is recorded, so you can't retroactively pick a strike that
   made you look good.

You will very likely see direction accuracy near 50% and option P&L negative.
That gap is theta and the spread, and it is the reason "I was right about the
direction" is not a strategy.

---

## Data sources (all free, no key, no account)

| Purpose | Primary | Fallback |
|---|---|---|
| Equity spot | Yahoo v8 chart | Stooq daily CSV (end-of-day) |
| Option chain | Yahoo v7 options | none — degrades to spot-only scoring |
| Crypto spot | Coinbase public API | Yahoo v8 chart |
| News | ~20 RSS feeds | n/a |

Every snapshot records **which provider answered**, so when a number looks odd
you can see whether you were on the fallback. Yahoo's endpoints are unofficial
and will break eventually; when they do, the job goes red rather than storing
garbage quietly.

---

## Viewing this on another device

The pages are a plain URL on GitHub Pages. Open them on a second phone, a
tablet, or a desktop next to your broker app — bookmark it or add to home
screen. No login, no app, nothing to install. There is nothing here worth
protecting: public market data and your own logged guesses.

It does **not** connect to any brokerage account, including Webull, and it does
not need to in order to be watched anywhere. Your broker shows positions; this
shows whether the reasoning has been any good.

---

## Why not connect a broker (Webull, Robinhood, anything)

Webull does publish an **official, documented OpenAPI** — which is a genuine
difference from Robinhood, whose public API is crypto-only and whose equities
access is reverse-engineered. So the objection here is not "there's no API."

The objection is that **the system hasn't earned execution rights.** Connecting
any broker means credentials in the loop, a path from a logged guess to a real
order, and a blast radius measured in dollars rather than in a red X on a CI
job. Nothing about the record justifies that yet — and the Record page is
specifically built to tell you when, or whether, it ever does.

If that day comes, use an official documented API (Webull OpenAPI, Alpaca,
Tradier, Schwab), start on their paper endpoint, and only after 90+ days of
logged results.

---

## Why not Robinhood

Robinhood's official public API covers **crypto only**. Every "Robinhood Python
library" is reverse-engineered from their private mobile endpoints, which means
storing your username, password and MFA seed in a script, violating their terms,
and risking an account freeze with positions open. Likelihood: moderate.
Impact: catastrophic. It's a no.

If you eventually want real automated execution, use a broker with a documented
API — Alpaca, Tradier, or Schwab — and only after 90+ days of logged paper
results say there's something worth executing.

---

## Known limitations

- **GitHub cron drops runs.** Scheduled workflows get delayed or skipped under
  load. This is documented platform behaviour, not a bug to fix. A missed run is
  normal; the card shows staleness per rail so a drop is visible instead of
  silent.
- **No market holiday calendar.** A holiday shows up as a stale snapshot, which
  is loud and correct. Hardcoding a holiday list means trusting a list that goes
  out of date.
- **Yahoo may start requiring a cookie+crumb** for the options endpoint. If
  `doctor.py` reports the chain dead, that's the likely cause; scoring degrades
  to spot-only rather than breaking.
- **SQLite in git grows.** ~96 crypto rows/day. At a year you're looking at a
  few tens of MB with history. Fine. If it bothers you, prune `snapshots` older
  than 90 days — the `calls` and `outcomes` tables are the ones that matter.

---

## v1 audit — bugs found and fixed

Every one of these was in the first version. Each now has a regression test that
fails against the old code.

| # | Severity | Bug | Fix |
|---|---|---|---|
| A | **critical** | The card read `snapshots ORDER BY id DESC LIMIT 60` and picked latest-per-symbol from that window. Crypto writes 96 rows/day, equities 2 — so after ~15 hours **SPY vanished from the page entirely**, and the staleness check could no longer see the equities rail. A dead equities job would sit behind a green "all fresh" banner indefinitely. | Query newest row *per symbol* via `GROUP BY`. Tracked symbols now come from `config.json`, so one that never reports shows as **NO DATA** instead of silently missing. |
| B | major | News sorted `CASE tier WHEN 'primary' THEN 0 ELSE 1 END, id DESC` — every primary item outranked every press item forever, so a three-week-old Fed release sat above breaking news. Published dates were also stored as raw strings and compared as text, mixing RFC-822 and ISO-8601. | Dates normalised to epoch at write time (new `published_ts` column + migration). Primary gets a bounded 12-hour recency boost, not permanent top billing. Tier grouping removed — it reintroduced the same problem visually. |
| C | moderate | `n += con.total_changes and 0 or 0` — always zero. The run log reported items *fetched* as items *added*, so every run looked like it pulled 25 fresh headlines when nearly all were duplicates. | Use `cursor.rowcount`. Also reports how many items arrived undated. |
| D | moderate | `--skip-if-closed` gated on `market_is_open()`, which is False at 8:30am — the flag would have silently skipped the **entire pre-market run**, the one you act on. | Replaced with named sessions (`--only-sessions premarket,postclose`) and a new `market_session()`. |
| E | cosmetic | Calibration bars used `<span>` for track and fill; spans are inline, so height and width were ignored and every bar rendered as an empty stub. | `display:block`. |
| F | minor | `market_is_open()` returned True at exactly 16:00:00 ET. The bell is not a moment of trading. | Close is now exclusive. |
| G | minor | DST changeover is tested at 07:00Z but happens at 06:00Z/07:00Z — off by an hour twice a year, on a Sunday at 2am. | Documented rather than fixed; the cost of fixing exceeds the harm. |

**133 offline tests** now pass, up from 48.
