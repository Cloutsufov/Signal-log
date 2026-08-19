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

**The `.github` folder is the one that gets lost.** It starts with a dot, so
Finder, Windows Explorer and GitHub's drag-and-drop uploader all hide it. If
Actions says *"Get started with GitHub Actions — found 0 workflows"*, that
folder didn't make it. Step 1b below is the guaranteed fix.

1. github.com → **+** → **New repository**
2. Name it anything. **Public.** *(Public matters: Actions minutes are unlimited
   on public repos, which is what makes 24/7 crypto free. There are no secrets
   in this project — no keys, no credentials, nothing about you — so public is
   safe here.)*
3. Tick **Add a README file** so the repo initialises, then **Create**.
4. **Add file → Upload files** → upload the unzipped contents.

**Important:** upload the *contents* of the zip, not the folder containing
them. `scripts/` and `README.md` must sit at the top level of the repo. If you
see a folder named `ship-room` or `signal-log` in your repo's Code tab, that's
the problem — everything is one level too deep and GitHub won't find the
workflow.

### Step 1b — if Actions says "found 0 workflows"

The `.github` folder didn't upload. Create it by hand — this always works, on
phone or desktop, because you *type* the path instead of picking a hidden file:

1. In your repo: **Add file → Create new file**
2. In the filename box type exactly:
   `.github/workflows/signal.yml`
   (typing the `/` characters creates the folders as you go)
3. Paste the entire contents of `signal.yml` — it's included as a separate file
   alongside the zip for exactly this reason
4. **Commit changes**

That's the only workflow file. There used to be six; they were consolidated
into one specifically so there's only one thing that can go missing.

---

## Step 2 — give the robot write access

**Settings → Actions → General → Workflow permissions** → select
**Read and write permissions** → **Save**.

Without this every job fails on the final `git push`. It is the single most
common reason a setup like this silently does nothing.

---

## Step 3 — press the one button

**Actions** tab → **signal log** → **Run workflow** → leave the action set to
**bootstrap** → **Run workflow**.

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

1. **Actions runs itself** every 30 minutes. It snapshots BTC and ETH, pulls
   news, scores anything that has matured, and rewrites `PROMPT.md`.
2. **Open `PROMPT.md`** in the repo. Copy it. Paste into Claude.
3. Claude replies with a direction, a confidence, and one line of reasoning.
4. **Actions → signal log → Run workflow** → action **record** → pick
   **direction** and **confidence** from the dropdowns, type the two sentences,
   Run. *(No JSON. A single-line web form eats pasted JSON, so the form doesn't
   ask for any.)*
5. Tomorrow's run scores it automatically and the Record page updates itself.

**One open call per symbol.** A second call is refused while the first is
still unscored — a duplicated call double-counts one opinion and biases the
record. Pass `--force` locally if you ever genuinely mean two.

That's it. No terminal at any point.

---

## Every button, and what it does

There is **one workflow**, called **signal log**, with a dropdown.

| Run it with action… | What happens |
|---|---|
| **bootstrap** | First run: probe every source, prune dead feeds, pull all prices + news, write the prompt, build the pages |
| **fetch** | Pull everything and score, right now |
| **record** | Record a call — symbol, direction and confidence dropdowns, two sentences |
| **doctor** | Health check only; writes `HEALTH.md` |

And it runs itself on a schedule:

| When | What |
|---|---|
| every 30 min, 24/7 | BTC/ETH snapshot, news, scoring, prompt, rebuild |
| weekdays 8:30am + 4:30pm ET | equity snapshot — **currently parked**, see below |
| Mondays | source health check |

### Why equities are parked

Every free keyless equity source (Yahoo, Stooq) returns **HTTP 429 in ~50ms**
from a GitHub Actions runner. That is the IP being rejected, not our traffic
being throttled. Crypto works because Coinbase doesn't do that.

SPY, QQQ and IWM therefore sit in `equities_parked` in `config.json`. They are
disclosed on the page with the reason rather than claimed-and-broken. All the
equity and option-chain code is untouched and still tested — move them back
into `equities` the day a quote key exists.

### What "direction-only scoring" means

With no option chain there is no theta and no spread to measure, so a call is
graded purely on whether spot moved the right way. That is the flattering half
of the measurement, and the pages say so on every screen. It clears itself
automatically the moment chain data arrives.

---

## When something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Every job fails at the push step | Workflow permissions | Step 2 above |
| Pages 404 | Pages not enabled, or wrong folder | Step 4 — must be `/docs` |
| Card says **PIPELINE DOWN** | A source died | Actions → signal log → action `doctor` |
| Option context section says "unavailable" | No free chain source will serve this IP | Expected. Spot scoring still works; option P&L doesn't. |
| A call is **REFUSED** | An earlier call on that symbol is still unscored | Correct behaviour — wait for it to mature |
| The **LIVE** badge never appears | The browser couldn't reach Coinbase's socket | Display only; the log is unaffected |
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
