# Bratislava 2-room rental tracker

Checks nehnutelnosti.sk and bazos.sk every morning, keeps the 2-room flats in
Petržalka, Ružinov, Karlova Ves, Nové Mesto and Rača that are renovated, have a
balcony and are on the 2nd floor or higher, and computes the real monthly cost:

```
effective = rent + energies + provision / 12
```

Results go to a sortable web page and new matches are sent to Telegram.

| Section | Rule |
|---|---|
| Matches | effective ≤ 800 € and every criterion confirmed |
| Near misses | 800 < effective ≤ 820 € |
| Needs a manual check | price fits, but floor, balcony, condition or rent is not stated |
| Recently removed | disappeared from the portal in the last 30 days (probably rented) |
| Excluded | failed a rule, with the reason; use it to spot filter mistakes |

Dropped entirely: rent + energies below 600 € (suspicious).
Flagged ⚠️: energies not stated (price shown as "≥"), provision assumed as 1 month's rent.

## Setup (about 20 minutes, no coding)

### 1. Telegram bot
1. In Telegram, open **@BotFather**, send `/newbot`, pick a name. Copy the **token** it gives you.
2. Open your new bot and send it any message (e.g. "hi").
3. In a browser open `https://api.telegram.org/bot<TOKEN>/getUpdates` (put your token in).
   Find `"chat":{"id":123456789` and copy that number. This is your **chat ID**.

### 2. GitHub repository
1. Create a free account at github.com.
2. Click **New repository**, name it e.g. `byt-tracker`, choose **Public**, create it.
3. Click **uploading an existing file** and drag in everything from this folder.
   The `.github` folder is hidden on some computers. If it doesn't upload, use
   **Add file → Create new file**, type the name `.github/workflows/track.yml`,
   and paste the contents of that file.

### 3. Secrets and page
1. Repository **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_BOT_TOKEN` = the token
   - `TELEGRAM_CHAT_ID` = the chat ID
2. **Settings → Pages**: Source "Deploy from a branch", branch `main`, folder `/docs`. Save.
   Your page address is `https://<your-username>.github.io/byt-tracker/`.
3. Back in **Secrets and variables → Actions**, open the **Variables** tab and add
   `PAGE_URL` = that address (Telegram messages will link to it).

### 4. First run
**Actions** tab → **Track flats** → **Run workflow**. After 5–15 minutes you get a
Telegram message and the page fills in. From then on it runs daily at about 07:00.

## If something breaks

- **Telegram says a source returned no listings**: the site blocked GitHub's servers
  or changed its layout. Open the failed run in **Actions**, download the
  `debug-pages` artifact, and share the HTML so the parser can be fixed.
- **"Run failed" message**: open the run in **Actions** to see the error.
- **GitHub pauses scheduled runs** after long repository inactivity. The daily
  commits normally prevent this; if it happens, re-enable it in the Actions tab.
- **Blocked from GitHub's servers**: run it from your own computer instead
  (`pip install -r requirements.txt`, then `python -m tracker.main` via Windows Task Scheduler or cron).

## Tuning

All rules are in `tracker/config.py`: price limits, minimum floor, district keywords,
Bazos postal codes, request delays. After editing, the next run re-evaluates all
stored listings with the new rules.

The postal-code map for Bazos is a best-effort guess. If you see a listing in the
wrong district, fix the codes there.

## Local test

```
pip install -r requirements.txt
pytest -q
python -m tracker.main --offline tests/fixtures --no-alerts   # uses saved pages
```

## How it decides (known limits)

Floor, balcony, condition, energies and provision are read from free Slovak text
with pattern rules. They cover the common phrasings ("+ 250 € energie",
"vrátane energií", "provízia vo výške jedného nájmu", "4.NP", "francúzsky balkón"
is not a balcony, …) but ads are written by people, so:

- A listing can be misread. The Excluded section shows every reason, so check it
  during the first week.
- "N. podlažie" is used inconsistently in Slovakia; when it matters (2. podlažie)
  the floor is marked unknown instead of guessed.
- Days listed counts from the first time the tracker saw the ad (or the portal
  date if older). Bazos resets its date when an ad is bumped; reposts with the
  same text are detected and keep the original date.
- Optional extras (garage, parking) are not added to the price.

Scraping may conflict with the portals' terms. The tracker is deliberately gentle:
one run per day with 2–4.5 s pauses between requests, and detail pages are
fetched only for new or re-priced candidates.
