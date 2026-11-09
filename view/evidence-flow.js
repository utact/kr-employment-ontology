const clamp=t=>Math.max(0,Math.min(1,t));
const ease=t=>t<.5?4*t*t*t:1-(-2*t+2)**3/2;

export function evidenceNodes(keys,accepted,evidence,focused) {
  if(!Array.isArray(keys)||!Array.isArray(accepted))return [];
  const allowed=new Set(accepted),active=new Set(focused);
  return [...new Set(keys.filter(key=>allowed.has(key)&&evidence[key]?.nodeId)
    .map(key=>evidence[key].nodeId).filter(id=>active.has(id)))];
}

export function flowPoint(start,end,t) {
  const vertical=Math.abs(end.y-start.y)>Math.abs(end.x-start.x)*1.25;
  const bend=vertical?Math.max(30,Math.abs(end.y-start.y)*.42):Math.max(40,Math.abs(end.x-start.x)*.45);
  const direction=vertical?Math.sign(end.y-start.y):Math.sign(end.x-start.x);
  const a=vertical?{x:start.x,y:start.y+bend*direction}:{x:start.x+bend*direction,y:start.y};
  const b=vertical?{x:end.x,y:end.y-bend*direction}:{x:end.x-bend*direction,y:end.y};
  const u=1-t;
  return {x:u*u*u*start.x+3*u*u*t*a.x+3*u*t*t*b.x+t*t*t*end.x,
    y:u*u*u*start.y+3*u*u*t*a.y+3*u*t*t*b.y+t*t*t*end.y};
}

// Visualizes membership in the already submitted context, not additional API calls.
export class EvidenceFlow {
  constructor(graph,evidence,receiver) {
    this.graph=graph;this.evidence=evidence;this.receiver=receiver;
    this.port=receiver.querySelector('.thinking-port');this.label=receiver.querySelector('#thinking-status');
    this.canvas=document.createElement('canvas');this.canvas.className='evidence-flow-canvas';
    this.canvas.setAttribute('aria-hidden','true');this.canvas.hidden=true;document.body.append(this.canvas);
    this.ctx=this.canvas.getContext('2d');this.flights=[];this.accepted=[];this.current=null;
    this.motion=matchMedia('(prefers-reduced-motion: reduce)');
    this.resize=()=>{
      this.dpr=Math.min(devicePixelRatio||1,2);
      this.canvas.width=Math.round(innerWidth*this.dpr);this.canvas.height=Math.round(innerHeight*this.dpr);
    };
    this.resize();window.addEventListener('resize',this.resize);
    this.motion.addEventListener('change',()=>{if(this.motion.matches)this.clearFlights();});
    this.tick=this.tick.bind(this);
  }

  begin() {
    this.finish();this.active=true;this.phase='requesting';this.accepted=[];this.signature='';
    this.receiver.dataset.phase='requesting';
  }
  status(event) {
    if(!this.active)return;
    if(this.phase!==event.phase){
      this.wash?.cancel();this.spark?.cancel();this.labelTransition?.cancel();
      if(!this.motion.matches)this.labelTransition=this.label.animate([
        {opacity:.4,transform:'translateY(2px)'},{opacity:1,transform:'translateY(0)'}
      ],{duration:200,easing:'ease-out'});
    }
    this.phase=event.phase;this.receiver.dataset.phase=event.phase;
    if(event.phase==='requesting'&&Array.isArray(event.evidenceIds)){
      this.accepted=event.evidenceIds.filter(key=>typeof key==='string'&&this.evidence[key]);
      this.launch();
    }
    if(event.phase==='validating')this.clearFlights();
  }
  focus(event) {this.current=event;this.launch();}

  launch() {
    if(!this.active||!this.current||!this.ctx||!['requesting','reasoning','writing'].includes(this.phase))return;
    const ids=evidenceNodes(this.current.evidenceKeys,this.accepted,this.evidence,this.current.nodeIds);
    if(!ids.length)return;
    const signature=`${this.current.index}:${ids.join('|')}`;
    if(signature===this.signature)return;this.signature=signature;
    if(this.motion.matches){this.receiver.classList.add('has-evidence');return;}
    if(!this.destination())return;
    const now=performance.now();
    ids.forEach((id,i)=>this.flights.push({id,start:now+160+i*65,duration:590,arrived:false}));
    this.canvas.hidden=false;
    if(!this.raf)this.raf=requestAnimationFrame(this.tick);
  }

  destination() {
    const r=this.port.getBoundingClientRect();
    const panel=this.receiver.closest('.chat-panel').getBoundingClientRect();
    const scroller=this.receiver.closest('.chat-scroll').getBoundingClientRect();
    const x=r.left+r.width/2,y=r.top+r.height/2;
    if(!r.width||!panel.width||x<0||x>innerWidth||y<Math.max(0,scroller.top)||y>Math.min(innerHeight,scroller.bottom))return null;
    return {x,y};
  }
  origin(id) {
    const node=this.graph.byId.get(id);if(!node)return null;
    const r=this.graph.canvas.getBoundingClientRect(),p=this.graph.screen(node);
    if(p.x<6||p.x>r.width-6||p.y<6||p.y>r.height-6)return null;
    const x=r.left+p.x,y=r.top+p.y;
    return x>=0&&x<=innerWidth&&y>=0&&y<=innerHeight?{x,y}:null;
  }

  absorb() {
    this.receiver.classList.add('has-evidence');
    this.wash?.cancel();this.spark?.cancel();
    const tint=getComputedStyle(this.receiver).getPropertyValue('--phase-rgb').trim();
    this.wash=this.receiver.animate([
      {boxShadow:`inset 0 0 0 1px rgb(${tint}/.38), 0 0 22px rgb(${tint}/.15)`,backgroundColor:`rgb(${tint}/.2)`},
      {boxShadow:`inset 0 0 0 1px rgb(${tint}/0), 0 0 0 rgb(${tint}/0)`,backgroundColor:`rgb(${tint}/.09)`}
    ],{duration:560,easing:'cubic-bezier(.16,1,.3,1)'});
    this.spark=this.port.animate([
      {transform:'scale(1.2)',filter:`drop-shadow(0 0 5px rgb(${tint}))`},
      {transform:'scale(1)',filter:`drop-shadow(0 0 0 rgb(${tint}/0))`}
    ],{duration:440,easing:'cubic-bezier(.16,1,.3,1)'});
  }

  tick(now) {
    this.raf=null;
    const c=this.ctx;c.setTransform(this.dpr,0,0,this.dpr,0,0);c.clearRect(0,0,innerWidth,innerHeight);
    const end=this.destination();
    if(!this.active||!end||document.hidden){this.clearFlights();return;}
    this.flights=this.flights.filter(f=>now<f.start+f.duration+230);
    for(const f of this.flights){
      const raw=(now-f.start)/f.duration;if(raw<0)continue;
      const start=this.origin(f.id);if(!start)continue;
      if(raw>=1){
        if(!f.arrived){f.arrived=true;this.absorb();}
        const p=(now-f.start-f.duration)/230;
        c.strokeStyle=`rgba(176,245,209,${(1-p)*.5})`;c.lineWidth=1;
        c.beginPath();c.arc(end.x,end.y,6+16*p,0,Math.PI*2);c.stroke();continue;
      }
      const head=ease(clamp(raw)),tail=Math.max(0,head-.23),fade=Math.min(1,raw*8,(1-raw)*8);
      const point=flowPoint(start,end,head),last=flowPoint(start,end,tail);
      c.save();c.globalAlpha=fade;
      c.lineWidth=.65;c.strokeStyle='#8dd3ae22';c.beginPath();
      for(let i=0;i<=36;i++){const p=flowPoint(start,end,i/36);i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y);}c.stroke();
      const gradient=c.createLinearGradient(last.x,last.y,point.x+.01,point.y+.01);
      gradient.addColorStop(0,'#85ddb000');gradient.addColorStop(.6,'#8ee7bc66');gradient.addColorStop(1,'#d1ffe5');
      c.strokeStyle=gradient;c.lineWidth=2.4;c.shadowColor='#89e7b7';c.shadowBlur=10;c.beginPath();
      for(let i=0;i<=20;i++){const p=flowPoint(start,end,tail+(head-tail)*i/20);i?c.lineTo(p.x,p.y):c.moveTo(p.x,p.y);}c.stroke();
      c.fillStyle='#e3ffef';c.beginPath();c.arc(point.x,point.y,2.25,0,Math.PI*2);c.fill();c.shadowBlur=0;
      if(raw<.3){c.strokeStyle=`rgba(168,238,200,${(1-raw/.3)*.7})`;c.lineWidth=.8;
        c.beginPath();c.arc(start.x,start.y,6+raw*38,0,Math.PI*2);c.stroke();}
      c.restore();
    }
    this.canvas.dataset.sourceCount=String(this.flights.length);
    if(this.flights.length)this.raf=requestAnimationFrame(this.tick);else this.clearFlights();
  }

  clearFlights() {
    cancelAnimationFrame(this.raf);this.raf=null;this.flights=[];
    this.ctx?.clearRect(0,0,this.canvas.width,this.canvas.height);this.canvas.hidden=true;
    this.canvas.dataset.sourceCount='0';
  }
  finish() {
    this.active=false;this.clearFlights();this.wash?.cancel();this.spark?.cancel();this.labelTransition?.cancel();
    this.receiver.classList.remove('has-evidence');delete this.receiver.dataset.phase;
  }
}
