import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runScenario} from './scenario.js';
import {indexNeighbors, connectedNodes} from './graph.js';

const data=JSON.parse(readFileSync(new URL('./data/vault.json',import.meta.url),'utf8'));

test('시행일 전날과 당일에 다른 규정을 선택한다',()=>{
  const before=runScenario(data,'2025-12-31');
  const after=runScenario(data,'2026-01-01');
  assert.equal(before.cap,66000);
  assert.equal(before.selectedEvidence,'previous');
  assert.equal(after.cap,68100);
  assert.equal(after.selectedEvidence,'current');
  assert.equal(before.events[2].passed,false);assert.equal(after.events[2].passed,true);
  assert.equal(before.events[3].excludedEvidence,'current');
});
test('호버 연결은 방향과 중복 관계에 관계없이 직접 이웃만 포함한다',()=>{
  const nodes=['a','b','c','d'].map(id=>({id}));
  const neighbors=indexNeighbors(nodes,[{source:'a',target:'b'},{source:'b',target:'a'},{source:'c',target:'a'},{source:'c',target:'d'}]);
  assert.deepEqual([...connectedNodes(neighbors,['a'])].sort(),['a','b','c']);
  assert.equal(neighbors.get('a').size,2);
  assert.deepEqual([...connectedNodes(neighbors,['d'])].sort(),['c','d']);
});
test('선택과 활성 노드의 연결을 함께 강조할 수 있다',()=>{
  const neighbors=indexNeighbors(data.nodes,data.edges);
  const active=[data.scene.cap,data.scene.rate];
  const highlighted=connectedNodes(neighbors,active);
  for(const edge of data.edges)if(active.includes(edge.source)||active.includes(edge.target)){
    assert.ok(highlighted.has(edge.source));assert.ok(highlighted.has(edge.target));
  }
});
test('현재 시나리오 결과는 원문에서 내보낸 값으로 산정한다',()=>{
  const changed=structuredClone(data);changed.scenario.currentBaseCap=120000;
  assert.equal(runScenario(changed,'2026-09-30').cap,72000);
});
test('지원 범위를 벗어나거나 존재하지 않는 날짜를 거부한다',()=>{
  for(const value of ['2024-12-31','2026-10-15','2028-01-01','2025-02-29','2026-13-01','2026-02-30','','2026-1-1']){
    assert.throws(()=>runScenario(data,value),Error,value);
  }
});
test('실행 기록은 존재하는 노드와 원문만 참조한다',()=>{
  const run=runScenario(data,'2026-09-30');const nodes=new Set(data.nodes.map(n=>n.id));
  assert.equal(run.events.length,6);
  assert.equal(run.llmUsed,false);
  for(const event of run.events){
    for(const id of event.nodeIds)assert.ok(nodes.has(id));
    for(const key of event.evidenceKeys)assert.ok(data.evidence[key].text.length>0);
  }
  assert.ok(run.provenance.vaultFingerprint.length===64);
});
test('필수 근거가 사라지면 계산을 중단한다',()=>{
  const changed=structuredClone(data);delete changed.evidence.transition;
  assert.throws(()=>runScenario(changed,'2025-12-31'),/근거가 누락/);
});
test('시간은 실제 시계의 실행 구간을 측정한다',()=>{
  let t=0;const run=runScenario(data,'2026-01-01',()=>t+=2);
  assert.equal(run.durationMs,14);
  assert.deepEqual(run.events.map(e=>e.elapsedMs),[2,4,6,8,10,12]);
});
