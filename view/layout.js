const STORAGE_KEY='employment-view-panels-v1';
const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));

export function panelWidths(width,left,right) {
  const available=Math.max(0,width-20),sideMin=Math.min(200,available/3);
  const graphMin=Math.min(320,available-2*sideMin),budget=available-graphMin;
  left=Math.max(sideMin,left);right=Math.max(sideMin,right);
  if(left+right>budget){
    const excess=left+right-2*sideMin,space=budget-2*sideMin;
    left=sideMin+(left-sideMin)*space/excess;
    right=sideMin+(right-sideMin)*space/excess;
  }
  return {left,right,graph:available-left-right,available,sideMin,graphMin};
}

export function setupPanelResize(workspace) {
  const handles=[...workspace.querySelectorAll('.panel-divider')];
  const desktop=matchMedia('(min-width: 801px)');
  let ratios={left:.23,right:.23},sizes,drag=null,lastWidth=0;
  try {
    const saved=JSON.parse(localStorage.getItem(STORAGE_KEY));
    if(saved&&['left','right'].every(key=>Number.isFinite(saved[key])&&saved[key]>0&&saved[key]<1))ratios=saved;
  } catch {}
  const save=()=>{
    ratios={left:sizes.left/sizes.available,right:sizes.right/sizes.available};
    try{localStorage.setItem(STORAGE_KEY,JSON.stringify(ratios));}catch{}
  };
  const paint=()=>{
    workspace.style.setProperty('--left-panel',`${sizes.left}px`);
    workspace.style.setProperty('--right-panel',`${sizes.right}px`);
    handles.forEach(handle=>{
      const side=handle.dataset.side,other=side==='left'?'right':'left';
      handle.setAttribute('aria-valuemin',String(Math.round(sizes.sideMin)));
      handle.setAttribute('aria-valuemax',String(Math.round(sizes.available-sizes[other]-sizes.graphMin)));
      handle.setAttribute('aria-valuenow',String(Math.round(sizes[side])));
      handle.setAttribute('aria-valuetext',`${Math.round(sizes[side])}픽셀`);
    });
  };
  const fit=()=>{
    if(!desktop.matches)return;
    const width=workspace.getBoundingClientRect().width;
    if(width===lastWidth&&sizes)return;
    lastWidth=width;
    sizes=panelWidths(width,(width-20)*ratios.left,(width-20)*ratios.right);paint();
  };
  const setSide=(side,value)=>{
    const other=side==='left'?'right':'left';
    sizes[side]=clamp(value,sizes.sideMin,sizes.available-sizes[other]-sizes.graphMin);
    sizes.graph=sizes.available-sizes.left-sizes.right;paint();
  };
  const reset=()=>{ratios={left:.23,right:.23};lastWidth=0;fit();save();};
  const finish=()=>{
    if(!drag)return;
    drag=null;document.body.classList.remove('resizing-panels');save();
  };
  handles.forEach(handle=>{
    const side=handle.dataset.side,sign=side==='left'?1:-1;
    handle.addEventListener('pointerdown',event=>{
      if(event.button!==0||!desktop.matches)return;
      event.preventDefault();handle.focus();
      drag={side,startX:event.clientX,startWidth:sizes[side]};
      handle.setPointerCapture(event.pointerId);document.body.classList.add('resizing-panels');
    });
    handle.addEventListener('pointermove',event=>{
      if(drag?.side===side)setSide(side,drag.startWidth+(event.clientX-drag.startX)*sign);
    });
    handle.addEventListener('pointerup',finish);
    handle.addEventListener('pointercancel',finish);
    handle.addEventListener('lostpointercapture',finish);
    handle.addEventListener('dblclick',reset);
    handle.addEventListener('keydown',event=>{
      if(!desktop.matches)return;
      const increment=event.shiftKey?40:10;
      if(event.key==='ArrowLeft')setSide(side,sizes[side]-increment*sign);
      else if(event.key==='ArrowRight')setSide(side,sizes[side]+increment*sign);
      else if(event.key==='Home')setSide(side,0);
      else if(event.key==='End')setSide(side,sizes.available);
      else if(event.key==='Enter'){reset();event.preventDefault();return;}
      else return;
      event.preventDefault();save();
    });
  });
  new ResizeObserver(fit).observe(workspace);
  desktop.addEventListener('change',()=>{finish();lastWidth=0;fit();});
  fit();
}
