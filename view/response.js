export const phaseLabels={requesting:'답변 요청 중',reasoning:'추론 중',writing:'답변 작성 중',validating:'금액·출처 확인 중'};

export async function readModelResponse(response,onStatus) {
  if(!response.ok){const error=await response.json();throw new Error(error.error||'답변을 불러오지 못했습니다.');}
  if(!response.headers.get('Content-Type')?.includes('application/x-ndjson'))return response.json();
  const reader=response.body.getReader(),decoder=new TextDecoder();
  let buffer='',result;
  const consume=line=>{
    if(!line.trim())return;
    const event=JSON.parse(line);
    if(event.type==='error')throw new Error(event.error);
    if(event.type==='status'&&phaseLabels[event.phase])onStatus(phaseLabels[event.phase]);
    if(event.type==='result')result=event;
  };
  try{
    while(true){
      const {value,done}=await reader.read();
      buffer+=done?decoder.decode():decoder.decode(value,{stream:true});
      let end;
      while((end=buffer.indexOf('\n'))>=0){consume(buffer.slice(0,end));buffer=buffer.slice(end+1);}
      if(done){consume(buffer);break;}
    }
    if(!result)throw new Error('모델 응답이 완료되지 않았습니다. 다시 시도해 주세요.');
    return result;
  }finally{reader.releaseLock();}
}
