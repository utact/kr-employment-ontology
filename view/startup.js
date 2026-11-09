import {canReveal,STARTUP_TIMEOUT_MS} from './startup-timing.js';

const TAU=Math.PI*2, RAD=Math.PI/180;
const clamp=t=>Math.max(0,Math.min(1,t));
const smooth=t=>{t=clamp(t);return t*t*(3-2*t);};
const mix=(a,b,t)=>a+(b-a)*t;
const ease=t=>{t=clamp(t);return t<.5?4*t*t*t:1-(-2*t+2)**3/2;};

function project(lon,lat,centerLon,centerLat) {
  const l=(lon-centerLon)*RAD,p=lat*RAD,c=centerLat*RAD;
  return {x:Math.cos(p)*Math.sin(l),y:Math.cos(c)*Math.sin(p)-Math.sin(c)*Math.cos(p)*Math.cos(l),
    z:Math.sin(c)*Math.sin(p)+Math.cos(c)*Math.cos(p)*Math.cos(l)};
}

class Startup {
  constructor() {
    this.overlay=document.querySelector('#startup-overlay');
    this.canvas=document.querySelector('#startup-canvas');
    this.ctx=this.canvas.getContext('2d');
    this.started=performance.now();this.readyState=false;this.failed=false;this.done=false;
    this.motion=matchMedia('(prefers-reduced-motion: reduce)');
    this.reduced=this.motion.matches;
    try{this.compact=Boolean(sessionStorage.getItem('ontology-intro-seen'))&&!new URLSearchParams(location.search).has('intro');}
    catch{this.compact=false;}
    this.overlay.hidden=false;
    this.app=[document.querySelector('.topbar'),document.querySelector('main')];
    this.app.forEach(el=>{el.inert=true;});
    this.resize=()=>{
      this.width=innerWidth;this.height=innerHeight;this.dpr=Math.min(devicePixelRatio||1,2);
      this.canvas.width=Math.round(this.width*this.dpr);this.canvas.height=Math.round(this.height*this.dpr);
      this.needsDraw=true;
    };
    this.resize();window.addEventListener('resize',this.resize);
    this.skip=()=>{this.skipped=true;this.overlay.classList.add('is-static');};
    document.querySelector('#skip-intro').addEventListener('click',this.skip);
    this.onKey=event=>{if(event.key==='Escape'){event.preventDefault();this.skip();}};
    window.addEventListener('keydown',this.onKey);
    this.onMotion=event=>{this.reduced=event.matches;if(this.reduced)this.skip();};
    this.motion.addEventListener('change',this.onMotion);
    if(this.reduced||this.compact||!this.ctx)this.overlay.classList.add('is-static');
    else this.loadGeometry();
    this.tick=this.tick.bind(this);this.frame=requestAnimationFrame(this.tick);
    this.watchdog=setTimeout(()=>this.finish(true),STARTUP_TIMEOUT_MS);
  }

  async loadGeometry() {
    try{
      const response=await fetch('./assets/intro-geometry.json',{signal:AbortSignal.timeout(4500)});
      if(!response.ok)throw new Error('intro geometry');
      const data=await response.json();
      if(this.done)return;
      this.geometry=data;
      this.outline=new Path2D();this.outlineLength=0;
      for(const polygon of data.korea.outlines)for(const ring of polygon){
        ring.forEach(([x,y],i)=>{
          if(i){this.outline.lineTo(x-48,y-64);this.outlineLength+=Math.hypot(x-ring[i-1][0],y-ring[i-1][1]);}
          else this.outline.moveTo(x-48,y-64);
        });
        this.outline.closePath();
      }
      this.needsDraw=true;
    }catch{
      this.overlay.classList.add('is-static');this.skipped=true;
    }
  }

  ready() {this.readyState=true;}
  fail() {this.failed=true;}

  tick(now) {
    if(this.done)return;
    const elapsed=now-this.started;
    if(this.ctx&&!this.reduced&&!this.compact&&!this.skipped&&(elapsed<2200||this.needsDraw)){
      this.draw(elapsed);this.needsDraw=false;
    }
    if(canReveal(elapsed,{ready:this.readyState,failed:this.failed,compact:this.compact,reduced:this.reduced||this.skipped})){
      this.finish(elapsed>=STARTUP_TIMEOUT_MS&&!this.readyState);return;
    }
    this.frame=requestAnimationFrame(this.tick);
  }

  finish(timedOut=false) {
    if(this.done)return;
    this.done=true;cancelAnimationFrame(this.frame);clearTimeout(this.watchdog);
    clearTimeout(window.startupFallbackTimer);
    window.removeEventListener('resize',this.resize);window.removeEventListener('keydown',this.onKey);
    this.motion.removeEventListener('change',this.onMotion);
    if(timedOut){
      const notice=document.querySelector('#error-notice');
      notice.textContent='화면 준비가 지연되고 있습니다. 잠시 후 새로고침해 주세요.';notice.hidden=false;
    }
    const restoreFocus=this.overlay.contains(document.activeElement);
    this.app.forEach(el=>{el.inert=false;});
    document.documentElement.classList.remove('is-booting');
    document.documentElement.classList.add('is-revealing');
    this.overlay.setAttribute('aria-hidden','true');
    this.overlay.inert=true;this.overlay.classList.add('is-leaving');
    if(restoreFocus)document.querySelector('#run-button')?.focus({preventScroll:true});
    setTimeout(()=>{this.overlay.hidden=true;document.documentElement.classList.remove('is-revealing');},this.reduced?0:280);
    if(this.readyState&&!this.failed)try{sessionStorage.setItem('ontology-intro-seen','1');}catch{}
  }

  draw(elapsed) {
    const ctx=this.ctx,w=this.width,h=this.height;
    ctx.setTransform(this.dpr,0,0,this.dpr,0,0);ctx.clearRect(0,0,w,h);
    const cx=w/2,cy=h/2-24,base=Math.min(218,w*.35,h*.32),mapScale=Math.min(2.65,w/150,h/210);
    const turn=ease(elapsed/960),zoom=ease((elapsed-900)/820),flatten=smooth((elapsed-1390)/360);
    const radius=base*Math.exp(Math.log(mapScale*640/base)*zoom);
    const lon=mix(64,127.5,turn),lat=mix(15,38.2,turn);
    const globeAlpha=(1-smooth((elapsed-1360)/410))*smooth(elapsed/230);
    const locate=(lng,lt)=>{const p=project(lng,lt,lon,lat);return {...p,x:cx+p.x*radius,y:cy-p.y*radius};};
    if(globeAlpha>.001){
      ctx.save();ctx.globalAlpha=globeAlpha;
      const glow=ctx.createRadialGradient(cx,cy,base*.7,cx,cy,base*1.4);
      glow.addColorStop(0,'#73b39b00');glow.addColorStop(.45,'#73b39b08');glow.addColorStop(1,'#73b39b00');
      ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
      ctx.lineWidth=.65;ctx.strokeStyle='#9ac8b426';
      const line=points=>{
        ctx.beginPath();let drawing=false;
        for(const point of points){const p=locate(...point);if(p.z<0){drawing=false;continue;}
          if(drawing)ctx.lineTo(p.x,p.y);else ctx.moveTo(p.x,p.y);drawing=true;}
        ctx.stroke();
      };
      for(let parallel=-60;parallel<=60;parallel+=30)line(Array.from({length:181},(_,i)=>[-180+i*2,parallel]));
      for(let meridian=-180;meridian<180;meridian+=30)line(Array.from({length:91},(_,i)=>[meridian,-90+i*2]));
      if(radius<Math.max(w,h)){
        ctx.beginPath();ctx.arc(cx,cy,radius,0,TAU);ctx.strokeStyle='#a2d1bc45';ctx.stroke();
      }
      if(this.geometry){
        const nodes=this.geometry.world.points.map(p=>locate(...p));
        ctx.strokeStyle='#91b8a83c';ctx.lineWidth=.55;ctx.beginPath();
        for(const [a,b] of this.geometry.world.edges){const p=nodes[a],q=nodes[b];
          if(p.z<.08||q.z<.08)continue;ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);}
        ctx.stroke();
        nodes.forEach((p,i)=>{
          if(p.z<=0||p.x<0||p.x>w||p.y<0||p.y>h)return;
          ctx.globalAlpha=globeAlpha*(.25+.65*p.z);
          ctx.fillStyle=i%7===0?'#b5d9c7':'#84b39d';
          ctx.beginPath();ctx.arc(p.x,p.y,(i%7===0?1.4:1.03)*Math.min(1.6,1+zoom),0,TAU);ctx.fill();
        });
      }
      ctx.restore();
    }
    if(!this.geometry)return;
    const koreaAlpha=mix(.12,1,smooth((elapsed-780)/780))*smooth(elapsed/300);
    const korea=this.geometry.korea;
    const points=korea.points.map(([x,y,lng,lt,tone])=>{
      const p=locate(lng,lt);
      return {x:mix(p.x,cx+(x-48)*mapScale,flatten),y:mix(p.y,cy+(y-64)*mapScale,flatten),z:p.z,tone};
    });
    ctx.save();ctx.globalAlpha=koreaAlpha;
    ctx.strokeStyle='#85b99e40';ctx.lineWidth=.65;ctx.beginPath();
    for(const [a,b] of korea.edges){const p=points[a],q=points[b];
      if(p.z<=0||q.z<=0)continue;ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);}
    ctx.stroke();
    for(const p of points){
      if(p.z<=0)continue;
      ctx.globalAlpha=koreaAlpha*(.58+.24*p.tone);
      ctx.fillStyle=`rgb(${Math.round(mix(117,183,p.tone))} ${Math.round(mix(162,218,p.tone))} ${Math.round(mix(141,194,p.tone))})`;
      const size=(.5+.4*p.tone**1.1)*mix(.7,mapScale,smooth((elapsed-780)/900));
      ctx.beginPath();ctx.arc(p.x,p.y,size,0,TAU);ctx.fill();
    }
    ctx.restore();
    const capture=smooth((elapsed-1600)/300);
    if(capture>0){
      ctx.save();ctx.translate(cx,cy);ctx.scale(mapScale,mapScale);
      ctx.strokeStyle='#b4e4cd';ctx.lineWidth=.48;ctx.globalAlpha=.45*capture;
      ctx.setLineDash([this.outlineLength*capture,this.outlineLength]);ctx.stroke(this.outline);ctx.setLineDash([]);
      ctx.restore();
      for(const start of [1630,1840]){
        const progress=(elapsed-start)/320;if(progress<0||progress>1)continue;
        ctx.save();ctx.translate(cx,cy);const scale=mapScale*(1+.055*progress);ctx.scale(scale,scale);
        ctx.globalAlpha=Math.sin(progress*Math.PI)*.48;ctx.strokeStyle='#b9edd2';ctx.lineWidth=.55;
        ctx.shadowColor='#95d4b6';ctx.shadowBlur=7;ctx.stroke(this.outline);ctx.restore();
      }
    }
  }
}

export const startup=new Startup();
