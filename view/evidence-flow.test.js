import test from 'node:test';
import assert from 'node:assert/strict';
import {evidenceNodes,flowPoint} from './evidence-flow.js';

const evidence={current:{nodeId:'cap'},previous:{nodeId:'cap'},rate:{nodeId:'rate'},
  effective:{nodeId:'transition'},transition:{nodeId:'transition'}};

test('서버가 입력으로 확인한 근거 중 현재 포커싱된 노드만 연결한다',()=>{
  assert.deepEqual(evidenceNodes(['previous','rate','invented'],['current','rate'],evidence,['cap','rate']),['rate']);
  assert.deepEqual(evidenceNodes(['current'],[],evidence,['cap']),[]);
  assert.deepEqual(evidenceNodes(['current'],['current'],evidence,['unrelated']),[]);
});
test('시행일과 경과조치가 같은 노트이면 연결을 중복하지 않는다',()=>{
  assert.deepEqual(evidenceNodes(['effective','transition'],['effective','transition'],evidence,['transition']),['transition']);
});
test('패널이 가로 또는 세로로 배치돼도 경로 양 끝은 실제 좌표와 일치한다',()=>{
  for(const [a,b] of [[{x:200,y:420},{x:940,y:300}],[{x:80,y:110},{x:95,y:710}]]){
    assert.deepEqual(flowPoint(a,b,0),a);assert.deepEqual(flowPoint(a,b,1),b);
    const middle=flowPoint(a,b,.5);
    assert.ok(Number.isFinite(middle.x)&&Number.isFinite(middle.y));
  }
});
