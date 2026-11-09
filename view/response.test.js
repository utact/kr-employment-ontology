import test from 'node:test';
import assert from 'node:assert/strict';
import {readModelResponse} from './response.js';

function streamResponse(events,cut=3) {
  const bytes=new TextEncoder().encode(events.map(event=>JSON.stringify(event)).join('\n')+'\n');
  return new Response(new ReadableStream({start(controller){
    for(let i=0;i<bytes.length;i+=cut)controller.enqueue(bytes.slice(i,i+cut));controller.close();
  }}),{headers:{'Content-Type':'application/x-ndjson'}});
}

test('분할 수신한 한국어를 복원하고 실제 상태 이벤트만 표시한다',async()=>{
  const labels=[];
  const result=await readModelResponse(streamResponse([
    {type:'status',phase:'requesting'},{type:'status',phase:'reasoning'},
    {type:'status',phase:'writing'},{type:'status',phase:'invented'},
    {type:'result',cap:68100,explanation:'하루 상한액은 68,100원입니다.'}
  ]),label=>labels.push(label));
  assert.deepEqual(labels,['답변 요청 중','추론 중','답변 작성 중']);
  assert.equal(result.explanation,'하루 상한액은 68,100원입니다.');
});

test('중단되거나 검증에 실패한 응답을 완료로 표시하지 않는다',async()=>{
  await assert.rejects(readModelResponse(streamResponse([{type:'status',phase:'reasoning'}]),()=>{}),/완료되지/);
  await assert.rejects(readModelResponse(streamResponse([{type:'error',error:'금액 불일치'}]),()=>{}),/금액 불일치/);
});

test('근거 표시는 서버가 보낸 입력 근거 식별자를 그대로 받는다',async()=>{
  const states=[];
  await readModelResponse(streamResponse([
    {type:'status',phase:'requesting',evidenceIds:['previous','rate']},
    {type:'result',cap:66000}
  ]),(label,state)=>states.push(state));
  assert.deepEqual(states[0].evidenceIds,['previous','rate']);
});
