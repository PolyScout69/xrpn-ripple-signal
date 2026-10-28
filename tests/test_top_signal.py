"""Executable regression checks for the homepage's 72-hour Top Investor Signal.

This uses the actual JavaScript scoring functions from app.js (not a separate
copy of the ranking logic), so UI changes cannot silently restore stale leads.
"""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TopSignalTests(unittest.TestCase):
    def test_top_signal_weights_and_72_hour_expiry(self):
        source = (ROOT / 'app.js').read_text(encoding='utf-8')
        self.assertIn('TOP_SIGNAL_WEIGHTS = Object.freeze({ importance: 35, freshness: 30, moon: 20, source: 15 })', source)
        self.assertIn('TOP_SIGNAL_WINDOW_MS = 72 * 60 * 60 * 1000', source)
        self.assertIn('TOP INVESTOR SIGNAL · 72H', source)
        self.assertNotIn("return [...items].sort((a,b)=>(b.score||0)", source)

        # Ubuntu GitHub Actions includes Node. Skip executable tests on a
        # minimal local Python setup that genuinely has no Node installed.
        if not shutil.which('node'):
            self.skipTest('Node is required for executable JavaScript ranking tests')

        start = source.index('  const TOP_SIGNAL_WINDOW_MS =')
        end = source.index('  function renderFeed()', start)
        functions = source[start:end]
        run = r"""
'use strict';
const assert = require('node:assert/strict');
const time = value => {const d=new Date(value);return Number.isFinite(+d)?+d:0};
const state={view:'overview'};
""" + functions + r"""
const now=Date.parse('2026-10-28T06:36:00Z');
function story(id,hoursAgo,impact='High',source_type='Official',moon=0,opts={}){
  return {id,impact,source_type,published_at:new Date(now-hoursAgo*3600000).toISOString(),
          moon_meters:[{value:moon,scenario:'reported'}],...opts};
}
const old=story('equity-facility',42.6,'High','Official',-1);
const newLead=story('ripple-trade-finance',18,'High','Official',2);
assert.equal(chooseFeature([old,newLead],now).id,'ripple-trade-finance',
             'a new material event should beat an older 99-point article');
assert.equal(topSignalScore(story('exact-72h',72,'High','Official',3),now)!==null,true);
assert.equal(topSignalScore(story('expired',72.0001,'High','Official',3),now),null);
assert.equal(chooseFeature([story('old-only',90)],now),null);
assert.equal(topSignalScore(story('bear',4,'High','Official',-3),now),
             topSignalScore(story('bull',4,'High','Official',3),now),
             'negative Moon signals must count by magnitude');
assert(topSignalScore(story('high',4,'High'),now)>topSignalScore(story('low',4,'Low'),now));
assert(topSignalScore(story('issuer',4),now)>topSignalScore(story('secondary',4,'High','Media'),now));
assert(topSignalScore(story('secondary',4,'High','Media',3),now)>
       topSignalScore(story('rumour',4,'High','Media',3,{moon_meters:[{value:3,scenario:'rumour'}]}),now));
assert.notEqual(topSignalScore(story('date-only-today',-5,'Medium','Official',1,{date_only:true}),now),null);
assert.equal(topSignalScore(story('future-dated',-5),now),null);
assert.equal(topSignalScore(story('date-only-tomorrow',-27,'Medium','Official',1,{date_only:true}),now),null);
state.view='high';assert.equal(chooseFeature([newLead],now),null);
state.view='overview';assert.equal(chooseFeature([],now),null);
"""
        result = subprocess.run(
            ['node', '-e', run], cwd=ROOT, capture_output=True,
            text=True, timeout=20, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + '\n' + result.stderr)


if __name__ == '__main__':
    unittest.main()
