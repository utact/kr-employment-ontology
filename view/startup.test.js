import test from 'node:test';
import assert from 'node:assert/strict';
import {canReveal,STARTUP_TIMEOUT_MS} from './startup-timing.js';

test('연출이 끝나도 준비되지 않은 화면을 공개하지 않는다',()=>{
  assert.equal(canReveal(3000),false);
  assert.equal(canReveal(3000,{ready:true}),true);
  assert.equal(canReveal(300,{ready:true}),false);
});
test('짧은 전환과 동작 줄이기도 실제 준비 완료를 기다린다',()=>{
  assert.equal(canReveal(1000,{compact:true}),false);
  assert.equal(canReveal(1000,{compact:true,ready:true}),true);
  assert.equal(canReveal(10,{reduced:true}),false);
  assert.equal(canReveal(10,{reduced:true,ready:true}),true);
});
test('초기화 실패와 제한 시간 초과가 진입을 영구 차단하지 않는다',()=>{
  assert.equal(canReveal(10,{failed:true}),true);
  assert.equal(canReveal(STARTUP_TIMEOUT_MS),true);
});
