# Signal — investor intelligence

**Live site:** https://polyscout69.github.io/xrpn-ripple-signal/

Clean, source-first investor news for **Evernorth Holdings (XRPN)**, **Ripple**, **XRP Ecosystem (XRPL)** and **Strategy (MSTR, formerly MicroStrategy)**.

## How Signal works

- Every day at 18:00 UTC, GitHub Actions runs `scripts/scan.py` and publishes `data/news.json` to the dashboard via GitHub Pages. GitHub may delay scheduled workflows.
- SEC EDGAR is monitored using the correct issuer identifiers: Evernorth `0002092592` and Strategy `0001050446`. It requires a repository variable `SEC_USER_AGENT` set to a descriptive name and real contact email (see below); no fake emails are used.
- Additional sources include Ripple's newsroom, Evernorth company releases, and focused news queries for each issuer and XRP Ledger developers, validators, upgrades, DeFi, tokenisation, regulation and institutional adoption.
- Stories about the same **underlying event** are collapsed into **one feed card**, preserving links to other reporting in *More sources*. SEC filings with different accession numbers remain separate.
- Filter stories by tracked entity, impact (High / Medium / Low), topic and recency. Saved stories and read status stay **only in your browser**. Search and CSV export use the currently selected filters.
- Source-health indicators are honest: `Setup needed` or `Error` means that channel is missing or failed, not that it succeeded.

### Enable both SEC filing sources

Open [Settings → Secrets and variables → Actions](https://github.com/PolyScout69/xrpn-ripple-signal/settings/variables/actions) and choose **New repository variable**.

Name: `SEC_USER_AGENT`

Value: `Signal investor research Your Name your-real-email@example.com` (replace with your actual name/email). This is required by SEC EDGAR's automated access policy. Because GitHub Actions repository variables are not secret, use a dedicated contact email if you prefer.

Then run the workflow manually in [Actions](https://github.com/PolyScout69/xrpn-ripple-signal/actions/workflows/daily-scan.yml), or wait until its next scheduled run.

### Investor-impact labels

The impact labels use transparent **heuristics**, not investment advice, ratings or price predictions. Read original disclosures and distinguish financing *facilities* from cash received, token purchases from per-share accretion, and partnership announcements from recognised revenue.

### Run locally

```
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
SEC_USER_AGENT='Research Contact research@example.com' python scripts/scan.py
python -m http.server 8000
```

The HTML, CSS and JavaScript do not require a build step or API key. Dependencies are for the scanner only. The data archive is a curated investor feed, **not a complete record of SEC filings or all market news**.
### Evidence-aware Moon Meter (v2)

The direction gauge is distinct from article **Impact** (importance). Moon scores range from −3 to +3, evaluated separately for XRP, XRPN, and MSTR.

* **±1:** plausible, modest or indirect effects (routine treasury buying, partnerships, capital raising, network upgrade delays).
* **±2:** material, supported evidence directly tied to the tracked token or shares (confirmed regulatory access, significant per-share dilution/accretion).
* **±3:** exceptional, strongly evidenced developments (e.g. a verified solvency catastrophe or a very large confirmed change in coin holdings per diluted share).
* **0:** no clear asset-specific directional catalyst in the available report.
* **— Not rated:** insufficient reliable information; notably generic SEC filing headings and unconfirmed partnership rumours. This **must not be interpreted as neutral**.

The score is a **headline/short-excerpt heuristic**; it does not read SEC attachments or price history, measure whether the market has already priced news in, or estimate probability/percentage of returns. Its evidence badge distinguishes primary-source from secondary reporting, not confidence in the price forecast. No artificial quota of bullish/bearish ratings is imposed.
