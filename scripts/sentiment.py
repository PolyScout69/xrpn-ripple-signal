"""Thirty-day asset-specific Moon Sentiment, derived from headline Moon Meters.

The index is a weighted *directional* summary, not a survey of every headline.
In particular, routine score-0 stories do not outweigh important catalysts.
It preserves downside, avoids double-counting near-identical reports and
labels weak coverage. It is neither a probability nor a price forecast.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import exp, log
import re

DAYS = 30
HALF_LIFE_DAYS = 17
IMPACT_WEIGHTS = {'High': 4.5, 'Medium': 2.25, 'Low': 1.0}
SOURCE_WEIGHTS = {'Official': 1.15, 'SEC': 1.15, 'Media': 1.0, 'News': 1.0}
SCENARIO_WEIGHTS = {'reported': 1.0, 'assumption': 0.90, 'rumour': 0.72}
NEUTRAL_DAMPENING = 0.08
ASSETS = ('XRPN', 'MSTR', 'LITS')
LABELS = {-3: 'Very bearish', -2: 'Bearish', -1: 'Slightly bearish',
           0: 'Neutral', 1: 'Slightly bullish', 2: 'Bullish', 3: 'Very bullish'}

# Event families are clustered within an ISO publication week, per asset and
# direction. This mitigates duplicated syndicated coverage while keeping
# positive and negative aspects of a financing separately assessable.
EVENT_FAMILIES = (
    ('equity-facility', r'\bequity (?:purchase )?facility\b|\b(?:cantor|80\.?7?m)\b.*\bfacility\b'),
    ('lits-repurchase', r'\b(?:lite strategy|lits)\b.*\b(?:repurchas\w*|buy[ -]?back\w*)\b|\b(?:repurchas\w*|buy[ -]?back\w*)\b.*\b(?:ltc|litecoin|lits)\b'),
    ('ltc-options-yield', r'\b(?:ltc|litecoin|treasury)\b.*\b(?:covered calls?|option premiums?)\b|\b(?:covered calls?|option premiums?)\b.*\b(?:ltc|litecoin|treasury)\b'),
    ('litvm-investment', r'\blitvm\b'),
    ('ltc-per-share', r'\b(?:ltc|litecoin)\s+(?:backing\s+)?per\s+(?:fully diluted\s+|diluted\s+)?share\b'),
    ('share-registration', r'\b11\.?5\s*m(?:illion)?\b.*\bshares?\b|\bregister\w*.*\bshares?\b.*\bwarrants?\b'),
    ('shareholder-approval', r'\b(?:shareholder|merger) (?:vote|approval)\b|\bshareholders? approve\b|\bmerger vote\b'),
    ('merger-complete', r'\bcomplet\w*\b.*\b(?:business combination|merger)\b'),
    ('treasury-yield', r'\bxrp\b.*\b(?:yield|lending|earn interest|put[s]?\s+(?:its\s+)?\w+\s+to work)\b|\b(?:yield|lending)\b.*\bxrp\b|\b(?:treasury|xrp)\b.*\b(?:coinbase|kraken|bitgo)\b'),
    ('per-share-target', r'\b(?:xrp|bitcoin|btc|ltc|litecoin)\s+per\s+(?:fully diluted\s+|diluted\s+)?share\b'),
    ('nasdaq-debut', r'\b(?:nasdaq|go(?:es|ing)? public)\b.*\b(?:debut|list(?:ed|ing)?|begins trading)\b'),
    ('uphold-access', r'\buphold\b.*\b(?:list|access|stock)\b'),
    ('treasury-drawdown', r'\b(?:treasury|xrp|bitcoin|btc|litecoin|ltc)\b.*\b(?:loss|loses?|lost|drops?|down)\b'),
    ('preferred-repurchase',
     r'\b(?:repurchas\w*|redeem\w*|buybacks?)\b.{0,100}\b(?:preferred|strc|strk|strf)\b'
     r'|\b(?:preferred|strc|strk|strf)\b.{0,100}\b(?:repurchas\w*|redeem\w*|buybacks?)\b'),
    ('btc-purchase', r'\b(?:acquir|buy|buys|bought|purchas)\w*\b.*\b(?:bitcoin|btc)\b'),
)


def _parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _event_key(item, asset, value, published):
    title = re.sub(r'\s+', ' ', str(item.get('title') or '').lower())
    for family, pattern in EVENT_FAMILIES:
        if re.search(pattern, title):
            iso = published.isocalendar()
            # Different sign = different implication of a mixed event.
            direction = '+' if value > 0 else '-' if value < 0 else '0'
            return f'{asset}:{family}:{iso.year}-W{iso.week:02d}:{direction}'
    # Do not cluster unrelated stories merely because they share the word XRP.
    return f'{asset}:story:{item.get("id") or item.get("url") or title}'


def _theme(key: str) -> str:
    parts = key.split(':', 2)
    return key if len(parts) < 2 or parts[1] == 'story' else parts[1]


def _weight(item, meter, age_days):
    impact = IMPACT_WEIGHTS.get(item.get('impact'), 1.0)
    source = SOURCE_WEIGHTS.get(item.get('source_type'), 1.0)
    scenario = SCENARIO_WEIGHTS.get(meter.get('scenario') or 'reported', 1.0)
    time_factor = exp(-log(2) * age_days / HALF_LIFE_DAYS)
    # Relevance score offers a modest tie-breaker but does not let being a
    # source's press release become synonymous with bullishness.
    relevance = max(0.9, min(1.12, 1.0 + (float(item.get('score') or 70) - 75) / 250))
    magnitude = 1.0 + 0.20 * max(0, abs(meter['value']) - 1)
    return impact * source * scenario * time_factor * relevance * magnitude


def _rounded_score(raw, directional_count):
    # No artificial directional rating when bullish and bearish news balance.
    size = abs(raw)
    if size < 0.35:
        return 0
    if size >= 2.3 and directional_count >= 2:
        step = 3
    elif size >= 1.35:
        step = 2
    else:
        step = 1
    return step if raw > 0 else -step


def aggregate_sentiment(items: list[dict], as_of: str | datetime) -> dict:
    """Produce XRPN/MSTR/LITS 30-day directional scores and an audit-friendly breakdown.

    Weight = materiality (4.5/2.25/1) × half-life decay (17 days)
             × source/specificity × scenario × exceptional-score multiplier.
    Non-directional news gets only an 8% denominator weight. Reports within
    the same economic-event family and ISO week contribute at most once.
    Repeated weekly headlines about the same catalyst are also discounted
    by 55%, 75%, then 85% to prevent single-theme dominance.
    """
    stamp = _parse_date(as_of) if isinstance(as_of, str) else as_of
    if not isinstance(stamp, datetime):
        raise ValueError('An unambiguous UTC as_of timestamp is required')
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)

    output = {}
    for asset in ASSETS:
        candidates = []
        for item in items:
            pub = _parse_date(item.get('published_at'))
            if pub is None:
                continue
            age = (stamp - pub).total_seconds() / 86400
            if age < 0 or age > DAYS:
                continue
            # Defensive: exclude naked SEC filing records, as the feed does.
            if item.get('source_type') == 'SEC' or item.get('category') == 'SEC filings':
                continue
            for meter in item.get('moon_meters') or []:
                if meter.get('asset') != asset:
                    continue
                score = meter.get('value')
                if type(score) is not int or not -3 <= score <= 3:
                    continue
                key = _event_key(item, asset, score, pub)
                candidates.append({
                    'asset': asset, 'value': score, 'weight': _weight(item, meter, age),
                    'key': key, 'family': _theme(key),
                    'published_at': item['published_at'], 'impact': item.get('impact'),
                    'source_type': item.get('source_type'),
                    'scenario': meter.get('scenario') or 'reported',
                    'title': item.get('title', ''), 'url': item.get('url', ''),
                    'id': item.get('id'), 'reason': meter.get('reason', ''),
                })

        grouped = defaultdict(list)
        for cand in candidates:
            grouped[cand['key']].append(cand)

        # Keep the strongest fully specified report per event/direction.
        # Confirmation counts are reported but never multiplied into score.
        events = []
        for group in grouped.values():
            leader = max(group, key=lambda x: (abs(x['value']), x['weight'], x['source_type'] == 'Official'))
            events.append({**leader, 'reports': len(group)})

        # A single repeated narrative can crowd out genuinely independent
        # themes. Discount its successive weekly appearances, even though
        # they are technically distinct announcements.
        themes = defaultdict(list)
        for event in events:
            themes[(event['family'], 1 if event['value'] > 0 else -1 if event['value'] < 0 else 0)].append(event)
        theme_discounts = (1.0, 0.45, 0.25, 0.15)
        for group in themes.values():
            group.sort(key=lambda x: x['weight'], reverse=True)
            for i, event in enumerate(group):
                event['weight'] *= theme_discounts[min(i, len(theme_discounts)-1)]

        directional = [x for x in events if x['value'] != 0]
        neutral = [x for x in events if x['value'] == 0]
        signed = sum(x['value'] * x['weight'] for x in directional)
        denominator = sum(x['weight'] for x in directional) + NEUTRAL_DAMPENING * sum(x['weight'] for x in neutral)
        raw = signed / denominator if denominator else 0.0
        rating = _rounded_score(raw, len(directional))
        distinct = len({x['family'] for x in directional})
        coverage = ('Limited coverage' if distinct < 3 else
                    'Moderate coverage' if distinct < 7 else
                    'Broad coverage')
        ranked = sorted(directional, key=lambda x: abs(x['value'] * x['weight']), reverse=True)
        leaders, seen_families = [], set()
        # Show genuinely different drivers instead of four variants of STRC.
        for event in ranked:
            signature = (event['family'], 1 if event['value'] > 0 else -1)
            if signature not in seen_families:
                leaders.append(event)
                seen_families.add(signature)
            if len(leaders) == 4:
                break
        output[asset] = {
            'value': rating, 'label': LABELS[rating],
            'raw_score': round(raw, 2),
            'window_days': DAYS,
            'as_of': stamp.isoformat().replace('+00:00', 'Z'),
            'stories': len(candidates),
            'independent_events': len(events),
            'directional_events': len(directional),
            'distinct_catalysts': distinct,
            'bullish_events': sum(x['value'] > 0 for x in directional),
            'bearish_events': sum(x['value'] < 0 for x in directional),
            'neutral_events': len(neutral),
            'coverage': coverage,
            'drivers': [{
                'id': x['id'], 'title': x['title'], 'value': x['value'],
                'impact': x['impact'], 'published_at': x['published_at'],
                'reports': x['reports'], 'scenario': x['scenario'],
                'reason': x['reason'], 'url': x['url'],
            } for x in leaders],
            'method': 'impact_decay_dedup_v2',
        }
    return output
