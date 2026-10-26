# Signal — investor intelligence

**Live dashboard:** https://polyscout69.github.io/xrpn-ripple-signal/

Independent investor news for **Evernorth Holdings (XRPN)**, **Ripple**, **XRP Ecosystem (XRPL)**, and **Strategy (MSTR)**.

## Sources and publishing

- Every day at approximately **18:00 UTC**, GitHub Actions runs `scripts/scan.py`, updates `data/news.json`, and deploys GitHub Pages.
- Signal monitors Ripple and Evernorth official announcements and targeted business and ecosystem news feeds, including Strategy's Bitcoin treasury activity and company developments.
- **Standalone SEC filing records are intentionally excluded** from news cards, source monitoring and the Moon Meter. A news report about material financing, partnerships, regulation or other events may still appear, but standalone filing entries do not.
- Multiple publications of the same event are grouped with additional source links.
- Source Health reflects **three** channels: Ripple official, Evernorth official, and issuer/ecosystem news.

## Moon Meter (−3 to +3)

The Moon Meter is a transparent, conservative headline-level directional heuristic for **XRP**, **XRPN** or **MSTR**, not a price forecast. It rates published news, not standalone filing entries. Scores range from −3 (very bearish), through 0 (neutral), to +3 (very bullish). Where evidence is insufficient, **Not rated (—)** is distinct from neutral. Materiality (Impact) is independent of direction (Moon Meter).

## Run locally

```bash
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests -v
python scripts/scan.py
python -m http.server 8000
```

The site is static HTML/CSS/JS; Python is used only for the scheduled collector. Sources can be delayed or incomplete; always verify underlying reports before any investment decision.
