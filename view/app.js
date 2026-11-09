import {VaultGraph, typeLabels} from './graph.js';
import {runScenario} from './scenario.js';
import {setupPanelResize} from './layout.js';
import {STEP_INTERVAL_MS,capturedFrameIndex,setupSpeedControl} from './playback.js';
import {readModelResponse} from './response.js';
import {startup} from './startup.js';
import {EvidenceFlow} from './evidence-flow.js';

const $ = selector => document.querySelector(selector);
const fmt = n => n.toLocaleString('ko-KR');
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let data, baselines, graph, evidenceFlow, execution=null, step=-1, timer=null, playing=false;
let baselineTimer=null, baselineDone=false, modelPending=false, playbackSpeed=1;
const delay = () => STEP_INTERVAL_MS / playbackSpeed;
const showError = message => {$('#error-notice').textContent=message;$('#error-notice').hidden=!message;};
const questionFor = date => `${date.replaceAll('-','.')} 퇴사한 일용근로자입니다. 하루 8시간 일했는데 구직급여는 하루 최대 얼마인가요?`;

function markdown(text) {
  const inline = text => escape(text)
    .replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  return text.split(/\n\s*\n/).map(block=>{
    if(block.split('\n').every(line=>line.startsWith('- ')))return `<ul>${block.split('\n').map(line=>`<li>${inline(line.slice(2))}</li>`).join('')}</ul>`;
    return `<p>${inline(block).replaceAll('\n','<br>')}</p>`;
  }).join('');
}

function pause() {clearTimeout(timer);timer=null;playing=false;$('#play-pause').textContent='▶';$('#play-pause').setAttribute('aria-label','탐색 기록 재생');}
function schedule() {
  clearTimeout(timer);if(!playing)return;
  timer=setTimeout(()=>{if(step<execution.events.length-1){showStep(step+1);schedule();}else pause();},delay());
}
function play() {
  if(!execution)return;
  if(step>=execution.events.length-1){resetStepTrack();showStep(0);}
  playing=true;$('#play-pause').textContent='Ⅱ';$('#play-pause').setAttribute('aria-label','탐색 기록 일시정지');schedule();
}
function showStep(index) {
  if(!execution)return;step=Math.max(0,Math.min(index,execution.events.length-1));
  const event=execution.events[step];
  revealSteps(execution.events,step);
  $('#step-counter').textContent=`${step+1}단계`;
  document.querySelectorAll('#step-track button').forEach((b,i)=>{b.classList.toggle('done',i<step);b.classList.toggle('current',i===step);b.setAttribute('aria-current',i===step?'step':'false');});
  graph.frame(execution.events,step);
  evidenceFlow?.focus(event);
  $('#graph-context').hidden=false;$('#graph-mode').textContent=event.title;$('#graph-detail').textContent=event.detail;
  $('#next-step').disabled=step===execution.events.length-1;
  if(step===execution.events.length-1)pause();
}

function replayBaseline() {
  clearTimeout(baselineTimer);baselineDone=false;updateComparison();
  $('#baseline-summary').hidden=true;
  const run=execution, response=run?.baseline;
  if(!response)return;
  $('#baseline-welcome').hidden=true;$('#baseline-conversation').hidden=false;
  $('#baseline-question').textContent=response.question;$('#baseline-answer').innerHTML='';
  $('#baseline-waiting').hidden=false;
  $('#baseline-cap').textContent='—';$('#baseline-time').textContent='—';
  $('#baseline-capture').hidden=false;$('#baseline-capture').href=response.screenshot;
  $('#baseline-captured').textContent=`${response.capturedAt.slice(0,10).replaceAll('-','.')} 수집`;
  $('#baseline-replay').disabled=true;$('#baseline-scroll').scrollTop=0;
  const started=performance.now();let displayed=-1;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reveal=()=>{
    if(execution!==run)return;
    const scroller=$('#baseline-scroll');
    const nearBottom=scroller.scrollHeight-scroller.scrollTop-scroller.clientHeight<65;
    const elapsed=performance.now()-started;
    const index=reduced?(elapsed>=response.durationMs?response.frames.length-1:-1):capturedFrameIndex(response.frames,elapsed);
    if(index>displayed){
      displayed=index;$('#baseline-waiting').hidden=true;
      $('#baseline-answer').innerHTML=response.frames[index].html;
      if(nearBottom)scroller.scrollTop=scroller.scrollHeight;
    }
    if(index<response.frames.length-1){
      const next=reduced?response.durationMs:response.frames[index+1].atMs;
      baselineTimer=setTimeout(reveal,Math.max(0,next-(performance.now()-started)));return;
    }
    baselineDone=true;
    $('#baseline-cap').textContent=`${fmt(response.cap)}원`;
    $('#baseline-time').textContent=`${(response.durationMs/1000).toFixed(1)}초`;
    $('#baseline-time').title='2026.11.09 1회 관측 · 질문 전송 직전부터 마지막 글자 표시까지';
    $('#baseline-replay').disabled=false;$('#baseline-summary').hidden=false;updateComparison();
  };
  baselineTimer=setTimeout(reveal,reduced?response.durationMs:response.frames[0].atMs);
}

function resetStepTrack() {
  $('#step-counter').textContent='';$('#step-track').replaceChildren();$('#step-track').classList.add('idle');
}
function revealSteps(events,index) {
  const track=$('#step-track');track.classList.remove('idle');
  for(let i=track.children.length;i<=index;i++){
    const button=document.createElement('button');button.dataset.step=String(i);button.className='entering';
    button.setAttribute('aria-label',`${i+1}단계: ${events[i].title}`);button.title=`${i+1}. ${events[i].title}`;
    track.append(button);
    requestAnimationFrame(()=>requestAnimationFrame(()=>button.classList.remove('entering')));
  }
}

function updateComparison() {
  const result=execution?.modelResponse;
  $('#amount-difference').hidden=!baselineDone||!result;
  if(!baselineDone||!result){$('#amount-difference').textContent='';return;}
  const delta=result.cap-execution.baseline.cap;
  $('#amount-difference').textContent=delta===0?'상한액 일치':`상한액 차이 ${delta>0?'+':''}${fmt(delta)}원`;
}

async function start(event) {
  event?.preventDefault();if(modelPending)return;
  showError('');pause();
  try{execution=runScenario(data,$('#separation-date').value);}
  catch(e){showError(e.message);return;}
  execution.question=questionFor(execution.separationDate);
  execution.baseline=baselines.responses.find(r=>r.separationDate===execution.separationDate&&r.question===execution.question)||null;
  $('#inspector').hidden=true;$('#search-results').hidden=true;$('#node-search').value='';
  $('#chat-empty').hidden=true;$('#conversation').hidden=false;$('#thinking-message').hidden=false;
  $('#answer-content').hidden=true;$('#answer-content').innerHTML='';$('#chat-scroll').scrollTop=0;
  $('#question-text').textContent=execution.question;$('#answer-cap').textContent='—';$('#model-time').textContent='생성 중';
  $('#play-pause').disabled=false;$('#next-step').disabled=false;$('#download-trace').disabled=false;
  resetStepTrack();
  replayBaseline();showStep(0);play();
  await requestAnswer(execution);
}

async function requestAnswer(run) {
  if(modelPending)return;
  modelPending=true;$('#run-button').disabled=true;$('#separation-date').disabled=true;$('#thinking-message').hidden=false;$('#answer-content').hidden=true;
  $('#answer-summary').hidden=true;
  evidenceFlow.begin();
  $('#model-time').textContent='생성 중';$('#thinking-status').textContent='답변 요청 중';
  try{
    const response=await fetch('./api/explain',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},body:JSON.stringify({separationDate:run.separationDate})});
    const result=await readModelResponse(response,(label,state)=>{
      if(execution===run){$('#thinking-status').textContent=label;evidenceFlow.status(state);}
    });
    if(execution!==run)return;
    run.modelResponse=result;run.llmUsed=true;
    const refs=result.evidenceIds;
    $('#answer-content').innerHTML=`<div class="answer-text">${markdown(result.explanation)}</div><div class="formula"><span>${fmt(run.baseCap)}원 × 60%</span><b>${fmt(run.cap)}원</b></div><div class="citations-label">근거</div>${refs.map((key,i)=>`<button class="citation" data-evidence="${escape(key)}"><span>${String(i+1).padStart(2,'0')}</span><span>${escape(data.evidence[key].title)}</span><span>↗</span></button>`).join('')}`;
    $('#answer-cap').textContent=`${fmt(result.cap)}원`;$('#model-time').textContent=`${(result.durationMs/1000).toFixed(1)}초`;
    $('#model-time').title='모델 요청부터 응답 완료까지';$('#answer-summary').hidden=false;updateComparison();
  }catch(e){
    if(execution===run){$('#answer-content').innerHTML=`<p class="model-error">${escape(e.message)}</p><button class="small-button" id="retry-model">다시 시도</button>`;$('#model-time').textContent='요청 실패';$('#retry-model').addEventListener('click',()=>requestAnswer(run));}
  }finally{
    evidenceFlow.finish();
    modelPending=false;$('#run-button').disabled=false;$('#separation-date').disabled=false;
    if(execution===run){$('#thinking-message').hidden=true;$('#answer-content').hidden=false;}
  }
}

function showNode(id,evidenceKey=null) {
  pause();
  if(!id){$('#inspector').hidden=true;graph.clearSelection();return;}
  const node=graph.byId.get(id);if(!node)return;
  $('#inspector').hidden=false;$('#inspector-type').textContent=typeLabels[node.type]||node.type;
  $('#inspector-title').textContent=node.name;$('#inspector-description').textContent=node.description;
  const ev=evidenceKey?data.evidence[evidenceKey]:null;
  const evidence=ev?[ev]:Object.values(data.evidence).filter(e=>e.nodeId===id&&(e!==data.evidence.previous||!execution?.current));
  $('#inspector-evidence').innerHTML=evidence.map(e=>`<div class="evidence-quote"><b>${escape(e.title)}</b>${escape(e.text)}</div>`).join('');
  $('#inspector-path').textContent=ev?`${ev.path} #${ev.anchor}`:`${node.path} · ${node.status}`;
  $('#inspector-link').hidden=!evidence[0]?.url;if(evidence[0]?.url)$('#inspector-link').href=evidence[0].url;
  graph.select(id);
}
function overview() {
  pause();graph.overview();$('#inspector').hidden=true;$('#graph-context').hidden=true;
}
function downloadTrace() {
  if(!execution)return;
  const blob=new Blob([JSON.stringify({...execution,exportedAt:new Date().toISOString()},null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`이직_실업급여_탐색기록_${execution.separationDate}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

async function init() {
  try{
    const [vaultResponse,baselineResponse,statusResponse]=await Promise.all([fetch('./data/vault.json'),fetch('./data/baseline-responses.json'),fetch('./api/status')]);
    if(!vaultResponse.ok||!baselineResponse.ok)throw new Error('데이터를 불러오지 못했습니다.');
    data=await vaultResponse.json();baselines=await baselineResponse.json();
    const status=await statusResponse.json();
    $('#answer-mode').textContent=status.configured?'실시간':'키 미설정';
    $('#answer-mode').title=status.model||'';
    $('#as-of').textContent=`데이터 기준 ${data.meta.asOf.replaceAll('-','.')}`;
    const statuteCount=(data.meta.classes.LegalResource||0)+(data.meta.classes.LegalResourceSubdivision||0);
    $('#about-knowledge-count').textContent=fmt(data.meta.nodeCount-statuteCount);
    $('#about-statute-count').textContent=fmt(statuteCount);
    document.querySelectorAll('[data-about-date]').forEach(el=>{el.textContent=data.meta.asOf.replaceAll('-','.');el.dateTime=data.meta.asOf;});
    $('#graph-count').textContent=`노드 ${fmt(data.meta.nodeCount)} · 관계 ${fmt(data.meta.relationCount)}`;
    graph=new VaultGraph($('#graph-canvas'),data,showNode);$('#graph-loading').hidden=true;
    evidenceFlow=new EvidenceFlow(graph,data.evidence,$('#thinking-message'));
    setupPanelResize($('#workspace'));
    resetStepTrack();
    setupSpeedControl($('#playback-speed'),$('#speed-options'),speed=>{playbackSpeed=speed;if(playing)schedule();});
    $('#run-button').disabled=false;
    $('#question-form').addEventListener('submit',start);
    $('#baseline-replay').addEventListener('click',replayBaseline);
    $('#play-pause').addEventListener('click',()=>playing?pause():play());
    $('#next-step').addEventListener('click',()=>{pause();showStep(step+1);});
    $('#step-track').addEventListener('click',e=>{const b=e.target.closest('[data-step]');if(b){pause();showStep(Number(b.dataset.step));}});
    $('#answer-content').addEventListener('click',e=>{const b=e.target.closest('[data-evidence]');if(b)showNode(data.evidence[b.dataset.evidence].nodeId,b.dataset.evidence);});
    $('#overview-button').addEventListener('click',overview);$('#reset-camera').addEventListener('click',overview);
    $('#zoom-in').addEventListener('click',()=>graph.zoom(1.3));$('#zoom-out').addEventListener('click',()=>graph.zoom(1/1.3));
    $('#close-inspector').addEventListener('click',()=>showNode(null));
    $('#expand-graph').addEventListener('click',()=>{
      const expanded=$('#workspace').classList.toggle('graph-expanded');
      $('#expand-graph').setAttribute('aria-label',expanded?'답변 함께 보기':'그래프 크게 보기');
      $('#expand-graph').title=expanded?'답변 함께 보기':'그래프 크게 보기';
    });
    $('#download-trace').addEventListener('click',downloadTrace);
    $('#node-search').addEventListener('input',()=>{
      const query=$('#node-search').value.trim(),target=$('#search-results');
      if(!query){target.hidden=true;return;}
      const results=data.nodes.filter(n=>n.name.toLowerCase().includes(query.toLowerCase())).slice(0,9);
      target.innerHTML=results.length?results.map(n=>`<button data-node="${escape(n.id)}"><span>${escape(n.name)}</span><small>${escape(typeLabels[n.type]||n.type)}</small></button>`).join(''):'<p>검색 결과 없음</p>';
      target.hidden=false;
    });
    $('#node-search').addEventListener('keydown',e=>{if(e.key==='Escape')$('#search-results').hidden=true;if(e.key==='Enter')$('#search-results button')?.click();});
    $('#search-results').addEventListener('click',e=>{const b=e.target.closest('[data-node]');if(b){$('#search-results').hidden=true;showNode(b.dataset.node);}});
    document.addEventListener('click',e=>{if(!e.target.closest('.search-field,.search-results'))$('#search-results').hidden=true;});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#about-dialog').open)showNode(null);});
    await Promise.all([document.fonts.ready,...[...document.querySelectorAll('.brand img,.official-header img,.baseline-welcome img')].map(img=>img.decode().catch(()=>{}))]);
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    startup.ready();
  }catch(e){showError(e.message);$('#graph-loading').textContent='데이터를 불러오지 못했습니다.';startup.fail();}
}
const aboutTabs=[...document.querySelectorAll('.about-tabs [role="tab"]')];
function selectAboutTab(tab,focus=false) {
  aboutTabs.forEach(item=>{
    const selected=item===tab;
    item.setAttribute('aria-selected',String(selected));item.tabIndex=selected?0:-1;
    document.getElementById(item.getAttribute('aria-controls')).hidden=!selected;
  });
  $('.about-body').scrollTop=0;
  if(focus)tab.focus();
}
aboutTabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>selectAboutTab(tab));
  tab.addEventListener('keydown',event=>{
    let next;
    if(event.key==='ArrowRight')next=(index+1)%aboutTabs.length;
    if(event.key==='ArrowLeft')next=(index+aboutTabs.length-1)%aboutTabs.length;
    if(event.key==='Home')next=0;
    if(event.key==='End')next=aboutTabs.length-1;
    if(next!==undefined){event.preventDefault();selectAboutTab(aboutTabs[next],true);}
  });
});
$('#about-button').addEventListener('click',()=>{selectAboutTab(aboutTabs[0]);$('#about-dialog').showModal();aboutTabs[0].focus();});
$('#close-about').addEventListener('click',()=>$('#about-dialog').close());
$('#about-dialog').addEventListener('click',e=>{if(e.target===$('#about-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
init();
