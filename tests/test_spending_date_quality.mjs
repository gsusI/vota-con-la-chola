import assert from 'node:assert/strict';
import {classifyDecisionDate,classifyDecisionDates,validDateRepresentation} from '../scripts/spending_date_quality.mjs';
const base={source_snapshot_date:'2025-06-30',source_record_id:'a',money_fact_id:'a'};
for(const [source,expected,status] of [
 ['0023-03-16','2023-03-16','corrected'],['0099-01-01','1999-01-01','corrected'],
 ['0205-01-24',null,'unresolved'],['0225-02-20',null,'unresolved'],
 ['2025-02-30',null,'unresolved'],['2024-02-29','2024-02-29','source'],
 ['1925-04-02','1925-04-02','source'],
]){
 const row=classifyDecisionDate({...base,decision_date:source});
 assert.equal(row.decision_date,expected);assert.equal(row.decision_date_status,status);
 assert.equal(row.decision_date_source,source);assert.ok(validDateRepresentation(row));
 assert.deepEqual(classifyDecisionDate(row),row);
}
assert.equal(validDateRepresentation({...base,decision_date:null,decision_date_source:'2025-01-01',decision_date_status:'unresolved'}),false);
const sorted=classifyDecisionDates(['0205-01-24','2025-01-01','0023-03-16'].map(decision_date=>({...base,decision_date})));
assert.deepEqual(sorted.map(r=>r.decision_date),['2023-03-16','2025-01-01',null]);
console.log('Date classification: literal preservation, leap dates, idempotence and unresolved ordering passed');
