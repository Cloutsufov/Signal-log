# Going live — phone only, no laptop, no terminal

The thing that kept this theoretical for three rounds was the assumption that
you needed to run Python somewhere. **You don't.** The GitHub Actions runner has
full internet access and does every fetch, every score, and every page build.
Your job is four button presses.

Total time: about ten minutes, most of it waiting.

---

## Step 1 — put the code on GitHub

**From a phone browser** (github.com works fine; the GitHub mobile app cannot
create repos with files, so use the browser):

1. github.com → **+** → **New repository**
2. Name it anything. **Public.** *(Public matters: Actions minutes are unlimited
   on public repos, which is what makes 24/7 crypto free. There are no secrets
   in this project — no keys, no credentials, nothing about you — so public is
   safe here.)*
3. Tick **Add a README file** so the repo initialises, then **Create**.
4. **Add file → Upload files** → upload the unzipped contents.

> Uploading a folder tree from a phone browser is genuinely annoying. If you
> have five minutes at a computer, this one step is much easier there — after
> it, you never need the computer again.

---

## Step 2 — give the robot write access

**Settings → Actions → General → Workflow permissions** → select
**Read and write permissions** → **Save**.

Without this every job fails on the final `git push`. It is the single most
common reason a setup like this silently does nothing.

---

## Step 3 — press the one button

**Actions** tab → **bootstrap (run this first)** → **Run workflow**.

*(GitHub asks you to enable workflows on a new repo the first time. Say yes.)*

In about 90 seconds it will:

1. Probe every data source — Yahoo, Stooq, Coinbase, all ~20 RSS feeds
2. Delete the dead feeds from `sources.json` automatically
3. Pull the first real prices for SPY, QQQ, IWM, BTC and ETH
4. Pull the first real headlines
5. Write today's `PROMPT.md`
6. Build all three pages
7. Commit the lot

**Green check = the system is live.** Read the run summary — it lists exactly
which sources answered and which are dead. That answer also lands in `HEALTH.md`
in the repo, readable on your phone any time.

**Red X = you know precisely what's broken**, which is better than not knowing.
`HEALTH.md` will say which source failed.

---

## Step 4 — turn on the web pages

**Settings → Pages** → Source: **Deploy from a branch** → Branch: `main`,
Folder: **`/docs`** → **Save**.

A minute later:

- Signals — `https://<you>.github.io/<repo>/`
- Record — `.../record.html`
- News — `.../news.html`

Open on any device. Add to home screen. No login, nothing to install. Put it
next to Webull on a second screen.

---

## The daily loop, from your phone

1. **Actions runs itself** at 8:30am and 4:30pm ET on weekdays. It snapshots
   prices and writes `PROMPT.md`.
2. **Open `PROMPT.md`** in the repo. Copy it. Paste into Claude.
3. Claude replies with JSON.
4. **Actions → "record a call" → Run workflow** → pick the symbol, paste the
   JSON, Run.
5. Tomorrow's run scores it automatically and the Record page updates itself.

That's it. No terminal at any point.

---

## Every button, and what it does

| Workflow | When | What |
|---|---|---|
| **bootstrap (run this first)** | manual, once | Full setup + first real data |
| **doctor (health check)** | manual, + weekly | Probes every source, writes `HEALTH.md`, optionally prunes dead feeds |
| **record a call** | manual, whenever you have a call | Refreshes the snapshot, records the call, locks the reference contract, rebuilds |
| **equities** | weekdays 8:30am + 4:30pm ET | SPY/QQQ/IWM snapshot, scoring, prompt, rebuild |
| **crypto** | every 30 min, 24/7 | BTC/ETH snapshot, scoring, rebuild |
| **news** | every 30 min | ~20 RSS feeds, rebuild |

---

## When something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Every job fails at the push step | Workflow permissions | Step 2 above |
| Pages 404 | Pages not enabled, or wrong folder | Step 4 — must be `/docs` |
| Card says **PIPELINE DOWN** | A source died | Actions → doctor → Run workflow |
| Boxes ②③④ empty | Yahoo's option chain endpoint is unavailable | Check `HEALTH.md`. Spot scoring still works; option P&L won't. |
| Scheduled runs don't fire | GitHub delays or drops scheduled workflows under load, and disables schedules entirely on repos with ~60 days of no activity | Documented platform behaviour. Push any commit to re-arm. |
| A feed you wanted got pruned | One bad run removed it | Revert that commit — it's one file |

---

## What "real" will actually look like

Expect, in order:

1. **Day 1** — a few dead feeds, pruned automatically. Normal.
2. **Week 1** — a handful of scored calls. The Record page will refuse to judge
   your confidence, correctly, because the sample is too small.
3. **Week 2–4** — direction hit rate hovering near 50%, average option P&L
   negative. That is the *expected* result, not a failure. It's theta and the
   spread doing what they always do.
4. **Day 30** — enough data to say something. Either the calibration table shows
   confidence carrying real signal, or it doesn't.

If it doesn't, you will have learned that for $0 and about five minutes a day,
which is the cheapest that lesson has ever been sold.
