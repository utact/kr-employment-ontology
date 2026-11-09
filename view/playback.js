export const STEP_INTERVAL_MS=1100;

export function capturedFrameIndex(frames,elapsedMs) {
  let low=0,high=frames.length;
  while(low<high){const mid=(low+high)>>>1;if(frames[mid].atMs<=elapsedMs)low=mid+1;else high=mid;}
  return low-1;
}

export function setupSpeedControl(button,list,onChange) {
  const options=[...list.querySelectorAll('[data-speed]')];
  let speed=1;
  const close=(focus=false)=>{list.hidden=true;button.setAttribute('aria-expanded','false');if(focus)button.focus();};
  const open=()=>{list.hidden=false;button.setAttribute('aria-expanded','true');options.find(o=>Number(o.dataset.speed)===speed).focus();};
  const select=option=>{
    speed=Number(option.dataset.speed);
    options.forEach(o=>o.setAttribute('aria-selected',String(o===option)));
    button.querySelector('span').textContent=`${speed}×`;button.setAttribute('aria-label',`재생 속도 ${speed}배`);
    close(true);onChange(speed);
  };
  button.addEventListener('click',()=>list.hidden?open():close());
  button.addEventListener('keydown',event=>{if(['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();open();}});
  options.forEach((option,index)=>{
    option.addEventListener('click',()=>select(option));
    option.addEventListener('keydown',event=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close(true);return;}
      const next=event.key==='ArrowDown'?(index+1)%options.length:event.key==='ArrowUp'?(index+options.length-1)%options.length:event.key==='Home'?0:event.key==='End'?options.length-1:null;
      if(next!==null){event.preventDefault();options[next].focus();}
    });
  });
  document.addEventListener('pointerdown',event=>{if(!button.parentElement.contains(event.target))close();});
  document.addEventListener('focusin',event=>{if(!button.parentElement.contains(event.target))close();});
}
