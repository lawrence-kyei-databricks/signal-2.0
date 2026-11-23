// Runs the DEPLOYED Signal2_Risk_Dashboard page script against every account's real briefing, with a minimal DOM shim.
// Usage (Node 18+):  node scripts/test_salesforce_page.js page.js briefings.json
//   page.js         the <script> body of the deployed Visualforce page (Tooling API: ApexPage.Markup)
//   briefings.json  [{"name": ..., "desc": <Account.Description JSON>}, ...] from the Salesforce org
// Fails (exit 1) if any account renders != 3 recommendations, if a recommendation differs from the source text,
// or if the page uses innerHTML (the shim throws), so LLM text can never render as markup.
const fs = require('fs');
const [pageFile, dataFile] = process.argv.slice(2);
const SCRIPT = fs.readFileSync(pageFile, 'utf8');
const accounts = JSON.parse(fs.readFileSync(dataFile, 'utf8'));

function el(id) {
  return { id, children: [], className: '', style: {}, _text: '',
    set textContent(v) { this._text = String(v); }, get textContent() { return this._text; },
    set innerHTML(v) { throw new Error('innerHTML used on ' + id); },
    appendChild(c) { this.children.push(c); return c; } };
}
const expected = s => (s || '').split(/(?:^|\n)\s*\d\.\s+/).map(t => t.trim()).filter(Boolean);

let failures = 0, runRateCards = 0;
for (const a of accounts) {
  const els = {};
  const document = { getElementById: id => (els[id] = els[id] || el(id)), createElement: t => el(t) };
  const src = SCRIPT.replace(/var rawDesc\s*=[^;]*;/, 'var rawDesc = ' + JSON.stringify(a.desc) + ';');
  new Function('document', 'window', 'setTimeout', src)(document, {}, () => {});
  const recs = (els.recList ? els.recList.children : []).map(li => li.children[1].textContent);
  const cards = (els.insightGrid ? els.insightGrid.children : []).map(d => [d.children[0].textContent, d.children[1].textContent]);
  const want = expected(JSON.parse(a.desc).recommendations);
  if (recs.length !== 3 || JSON.stringify(recs) !== JSON.stringify(want.slice(0, 3))) {
    failures++; console.log('FAIL', a.name, recs.length, 'recommendations rendered');
  }
  if (cards.some(c => c[0] === 'Revenue, last 6 mo vs 12-mo run rate')) runRateCards++;
}
console.log(`accounts: ${accounts.length} | recommendation failures: ${failures} | run-rate card shown: ${runRateCards}`);
process.exit(failures ? 1 : 0);
