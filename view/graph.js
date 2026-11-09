const colors = {
  LegalResource: '#aab2c3', LegalResourceSubdivision: '#8795aa', Rule: '#ae9be9',
  Criterion: '#6eafe0', Constraint: '#65b3ba', InformationConcept: '#7fc9ac',
  PublicService: '#dfb283', EvidenceType: '#dfb283', Concept: '#bb99af',
  ConceptScheme: '#ba8ab4', PublicOrganisation: '#7fbfac', Participation: '#bd95c6',
  Channel: '#ad9ed2', LifeEvent: '#d8c28b', BusinessEvent: '#d8c28b',
};
const labels = {source:'출처', implements:'법적 근거', appliesWhen:'적용 조건', requiredInput:'필요 입력',
  variable:'산정 결과', hasConcept:'판단 정보', isDerivedFrom:'근거 조문', cites:'인용', basedOn:'위임 근거'};
export const typeLabels = {LegalResource:'법령', LegalResourceSubdivision:'법령 조문', Rule:'산정 규칙',
  Criterion:'적용 조건', Constraint:'제약 조건', InformationConcept:'정보 항목', PublicService:'공공서비스',
  Concept:'개념', ConceptScheme:'개념 체계', EvidenceType:'증빙 서류', PublicOrganisation:'기관',
  Participation:'역할', Channel:'신청 경로', LifeEvent:'생활 사건', BusinessEvent:'사업 사건'};

export function indexNeighbors(nodes, edges) {
  const neighbors = new Map(nodes.map(n => [n.id, new Set()]));
  for (const edge of edges) {
    neighbors.get(edge.source)?.add(edge.target);
    neighbors.get(edge.target)?.add(edge.source);
  }
  return neighbors;
}

export function connectedNodes(neighbors, seeds) {
  const ids = new Set(seeds);
  for (const id of seeds) for (const neighbor of neighbors.get(id) || []) ids.add(neighbor);
  return ids;
}

export function graphBounds(nodes) {
  return nodes.reduce((b,n)=>({minX:Math.min(b.minX,n.x),maxX:Math.max(b.maxX,n.x),
    minY:Math.min(b.minY,n.y),maxY:Math.max(b.maxY,n.y)}),
    {minX:Infinity,maxX:-Infinity,minY:Infinity,maxY:-Infinity});
}

export function fitCamera(bounds,width,height) {
  return {x:(bounds.minX+bounds.maxX)/2,y:(bounds.minY+bounds.maxY)/2,
    k:Math.max(.01,Math.min(2.1,Math.max(1,width-56)/Math.max(1,bounds.maxX-bounds.minX),
      Math.max(1,height-96)/Math.max(1,bounds.maxY-bounds.minY)))};
}

export function constrainCamera(camera,bounds,width,height,nodes=[]) {
  const fit=fitCamera(bounds,width,height);
  const k=Math.max(fit.k,Math.min(5,camera.k));
  if(k===fit.k)return fit;
  const axis=(value,min,max,size)=>{
    const half=size/(2*k),margin=Math.min(48/k,half*.25);
    const low=min+half-margin,high=max-half+margin;
    return low>high?(min+max)/2:Math.max(low,Math.min(high,value));
  };
  const limited={x:axis(camera.x,bounds.minX,bounds.maxX,width),
    y:axis(camera.y,bounds.minY,bounds.maxY,height),k};
  if(nodes.length&&!nodes.some(n=>Math.abs(n.x-limited.x)*k<width/2-12&&Math.abs(n.y-limited.y)*k<height/2-12)){
    const nearest=nodes.reduce((best,n)=>(n.x-limited.x)**2+(n.y-limited.y)**2<(best.x-limited.x)**2+(best.y-limited.y)**2?n:best);
    limited.x=axis(nearest.x,bounds.minX,bounds.maxX,width);
    limited.y=axis(nearest.y,bounds.minY,bounds.maxY,height);
  }
  return limited;
}

export class VaultGraph {
  constructor(canvas, data, onSelect) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.data = data;
    this.nodes = data.nodes.map(n => ({...n, degree: 0}));
    this.byId = new Map(this.nodes.map(n => [n.id, n]));
    this.bounds = graphBounds(this.nodes);
    this.navigation = 'overview';
    this.edges = data.edges.map(e => ({...e, a: this.byId.get(e.source), b: this.byId.get(e.target)}));
    this.edges.forEach(e => {e.a.degree++; e.b.degree++;});
    this.neighbors = indexNeighbors(this.nodes, this.edges);
    this.onSelect = onSelect;
    this.camera = {x:0,y:0,k:1};
    this.target = {...this.camera};
    this.active = new Set(); this.visited = new Set(); this.sceneIds = new Set(Object.values(data.scene));
    this.focused = false; this.hovered = null; this.selected = null; this.dirty = true;
    this.activatedAt = 0; this.focusIds = []; this.edgeFlow = [];
    this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',e=>{this.reducedMotion=e.matches;this.dirty=true;});
    this.tooltip = document.querySelector('#graph-tooltip');
    this.mini = document.querySelector('#minimap-canvas');
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(canvas);
    this.bind(); this.resize(); this.animate();
  }
  resize() {
    const {width,height} = this.canvas.getBoundingClientRect();
    this.width = width; this.height = height;
    this.dpr = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(width * this.dpr); this.canvas.height = Math.round(height * this.dpr);
    if (this.navigation==='overview') this.overview(true);
    else if (this.navigation==='focus') {
      if(this.selected)this.select(this.selected);else this.focusNodes(this.focusIds);
    } else {
      this.limitTarget();this.camera=constrainCamera(this.camera,this.bounds,width,height,this.nodes);
    }
    this.dirty = true;
  }
  overview(immediate = false) {
    this.navigation='overview';
    this.target=fitCamera(this.bounds,this.width,this.height);
    this.limitTarget();
    if (immediate) this.camera = {...this.target};
    this.focused = false; this.selected = null; this.hovered = null; this.tooltip.hidden=true;this.dirty = true;
    document.querySelector('#graph-map').hidden = true;
  }
  focusScene() {
    this.focusNodes([...this.sceneIds]);
  }
  focusNodes(ids) {
    this.navigation='focus';
    this.focusIds=ids;
    const ns=ids.map(id=>this.byId.get(id)).filter(Boolean);if(!ns.length)return;
    const minX=Math.min(...ns.map(n=>n.x)),maxX=Math.max(...ns.map(n=>n.x));
    const minY=Math.min(...ns.map(n=>n.y)),maxY=Math.max(...ns.map(n=>n.y));
    const k=Math.min(2.1,(this.width-100)/Math.max(280,maxX-minX+120),(this.height-150)/Math.max(240,maxY-minY+100));
    this.target={x:(minX+maxX)/2,y:(minY+maxY)/2-30/k,k};
    this.limitTarget();
    this.focused = true; this.dirty = true;
    document.querySelector('#graph-map').hidden = false;
  }
  select(id) {
    const n = this.byId.get(id); if (!n) return;
    this.selected = id;
    this.navigation='focus';
    this.focused=true;this.focusIds=[id];document.querySelector('#graph-map').hidden=false;
    this.target = {x:n.x, y:n.y+30, k:Math.max(1.1,this.camera.k)};
    this.limitTarget();
    this.dirty = true;
  }
  clearSelection() {this.selected=null;this.dirty=true;}
  frame(events, index) {
    this.visited = new Set(events.slice(0,index+1).flatMap(e => e.nodeIds));
    this.active = new Set(events[index]?.nodeIds || []);
    this.selected = null;this.hovered=null;this.tooltip.hidden=true;
    this.activatedAt=performance.now();
    const seen=new Set();
    this.edgeFlow=this.edges.filter(e=>{
      if(!this.visited.has(e.source)||!this.visited.has(e.target)||(!this.active.has(e.source)&&!this.active.has(e.target)))return false;
      const key=[e.source,e.target].sort().join('|');if(seen.has(key))return false;seen.add(key);return true;
    });
    this.focusNodes(events[index]?.nodeIds||[...this.sceneIds]);
  }
  reset() {this.active.clear();this.visited.clear();this.overview();}
  limitTarget() {this.target=constrainCamera(this.target,this.bounds,this.width,this.height,this.nodes);}
  zoom(factor) {this.navigation='manual';this.target.k*=factor;this.limitTarget();this.dirty=true;}
  screen(n) {return {x:(n.x-this.camera.x)*this.camera.k+this.width/2,
    y:(n.y-this.camera.y)*this.camera.k+this.height/2};}
  bind() {
    let drag = null;
    this.canvas.addEventListener('wheel', e => {
      e.preventDefault();
      const rect=this.canvas.getBoundingClientRect(), px=e.clientX-rect.left-this.width/2, py=e.clientY-rect.top-this.height/2;
      const k=this.target.k,next=constrainCamera({...this.target,k:k*Math.exp(-e.deltaY*.001)},this.bounds,this.width,this.height).k;
      this.navigation='manual';
      this.target.x += px/k-px/next; this.target.y += py/k-py/next;this.target.k=next;this.limitTarget();this.dirty=true;
    },{passive:false});
    this.canvas.addEventListener('pointerdown', e => {
      if(e.button!==0)return;
      drag={x:e.clientX,y:e.clientY, moved:false};this.canvas.setPointerCapture(e.pointerId);this.canvas.style.cursor='grabbing';
    });
    this.canvas.addEventListener('pointermove', e => {
      if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
        if(Math.abs(dx)+Math.abs(dy)>2)drag.moved=true;
        if(drag.moved)this.navigation='manual';
        this.target.x-=dx/this.camera.k;this.target.y-=dy/this.camera.k;this.limitTarget();this.camera={...this.target};
        drag.x=e.clientX;drag.y=e.clientY;this.dirty=true;this.tooltip.hidden=true;return;}
      const rect=this.canvas.getBoundingClientRect(), x=e.clientX-rect.left,y=e.clientY-rect.top;
      this.hovered=this.nearest(x,y);this.canvas.style.cursor=this.hovered?'pointer':'grab';this.dirty=true;
      if(this.hovered){
        this.tooltip.replaceChildren();
        const title=document.createElement('b'),meta=document.createElement('span'),description=document.createElement('p');
        title.textContent=this.hovered.name;
        meta.textContent=`${typeLabels[this.hovered.type]||this.hovered.type} · 연결 ${this.neighbors.get(this.hovered.id).size}`;
        description.textContent=this.hovered.description;
        this.tooltip.append(title,meta,description);this.tooltip.hidden=false;this.positionTooltip();}
      else this.tooltip.hidden=true;
    });
    this.canvas.addEventListener('pointerup', e => {
      if(drag&&!drag.moved){const rect=this.canvas.getBoundingClientRect();const n=this.nearest(e.clientX-rect.left,e.clientY-rect.top);this.onSelect(n?.id===this.selected?null:n?.id||null);}
      drag=null;this.canvas.style.cursor='grab';
    });
    this.canvas.addEventListener('pointercancel',()=>{drag=null;this.canvas.style.cursor='grab';});
    this.canvas.addEventListener('pointerleave',()=>{this.hovered=null;this.tooltip.hidden=true;this.dirty=true;});
  }
  nearest(x,y) {
    let best=null,dist=144;
    for(const n of this.nodes){const p=this.screen(n);const d=(p.x-x)**2+(p.y-y)**2;
      if(d<dist){dist=d;best=n;}}
    return best;
  }
  positionTooltip() {
    if(!this.hovered||this.tooltip.hidden)return;
    const p=this.screen(this.hovered),gap=15,pad=10;
    const width=this.tooltip.offsetWidth,height=this.tooltip.offsetHeight;
    let x=p.x+gap,y=p.y-height/2;
    if(x+width>this.width-pad)x=p.x-width-gap;
    x=Math.max(pad,Math.min(x,this.width-width-pad));
    y=Math.max(pad,Math.min(y,this.height-height-pad));
    this.tooltip.style.left=`${x}px`;this.tooltip.style.top=`${y}px`;
  }
  draw() {
    const c=this.ctx,w=this.width,h=this.height;
    c.setTransform(this.dpr,0,0,this.dpr,0,0);c.clearRect(0,0,w,h);
    const pts=new Map(this.nodes.map(n=>[n.id,this.screen(n)]));
    const seeds=new Set([this.hovered?.id,this.selected].filter(Boolean));
    const interactive=seeds.size>0;
    const neighbors=connectedNodes(this.neighbors,interactive?seeds:this.active);
    const edgeAlpha=Math.max(.045,.16*fitCamera(this.bounds,w,h).k/this.camera.k);
    c.lineWidth=.7;c.strokeStyle=interactive?'rgba(126,151,167,.028)':this.focused?'rgba(124,157,169,.018)':`rgba(126,151,167,${edgeAlpha})`;c.beginPath();
    for(const e of this.edges){const a=pts.get(e.source),b=pts.get(e.target);c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);}c.stroke();
    if(this.visited.size||interactive){
      const used=new Set();
      for(const e of this.edges){
        const incident=interactive?(seeds.has(e.source)||seeds.has(e.target)):(this.active.has(e.source)||this.active.has(e.target));
        const visited=this.visited.has(e.source)&&this.visited.has(e.target);
        if(!incident&&!visited)continue;
        const pair=[e.source,e.target].sort().join('|');if(used.has(pair))continue;used.add(pair);
        c.strokeStyle=incident?'rgba(169,240,206,.92)':interactive?'rgba(147,217,182,.18)':'rgba(147,217,182,.60)';
        c.lineWidth=incident?1.7:1.1;
        const a=pts.get(e.source),b=pts.get(e.target);c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();
        if(!interactive&&this.focused&&this.active.has(e.source)&&this.active.has(e.target)&&labels[e.relation]){
          c.font='8px "Malgun Gothic", sans-serif';c.fillStyle='#789b89';c.textAlign='center';
          const midX=(a.x+b.x)/2,midY=(a.y+b.y)/2;
          c.fillStyle='#111c21';c.fillRect(midX-24,midY-7,48,12);c.fillStyle='#87ad99';c.fillText(labels[e.relation],midX,midY+2);
        }
      }
    }
    const progress=Math.min(1,Math.max(0,(performance.now()-this.activatedAt-75)/480));
    if(!this.reducedMotion&&!interactive&&progress>0&&progress<1){
      for(const e of this.edgeFlow){
        const source=pts.get(e.source),target=pts.get(e.target);
        const start=this.active.has(e.source)&&!this.active.has(e.target)?target:source;
        const end=start===source?target:source;
        const tail=Math.max(0,progress-.24),head={x:start.x+(end.x-start.x)*progress,y:start.y+(end.y-start.y)*progress};
        const tx=start.x+(end.x-start.x)*tail,ty=start.y+(end.y-start.y)*tail;
        const gradient=c.createLinearGradient(tx,ty,head.x+.01,head.y+.01);
        gradient.addColorStop(0,'#b6f3d400');gradient.addColorStop(1,'#d6ffe9');
        c.strokeStyle=gradient;c.lineWidth=2.3;c.beginPath();c.moveTo(tx,ty);c.lineTo(head.x,head.y);c.stroke();
        c.shadowColor='#9eebc6';c.shadowBlur=9;c.fillStyle='#e4fff0';c.beginPath();c.arc(head.x,head.y,2.1,0,Math.PI*2);c.fill();c.shadowBlur=0;
      }
    }
    for(const n of this.nodes){const p=pts.get(n.id);if(p.x<-15||p.x>w+15||p.y<-15||p.y>h+15)continue;
      const active=this.active.has(n.id), visited=this.visited.has(n.id), focus=this.focused&&this.sceneIds.has(n.id);
      const selected=this.selected===n.id,hovered=this.hovered?.id===n.id;
      const connected=neighbors.has(n.id);
      const radius=active||selected||hovered?5.5:focus?3.8:connected?3:Math.max(1.4,Math.min(5,1+Math.sqrt(n.degree)*.25)*Math.sqrt(this.camera.k));
      c.globalAlpha=interactive&&!connected ? .16 : (this.focused&&!visited&&!focus&&!connected) ? .25 : 1;
      if((active&&!interactive)||selected||hovered){const g=c.createRadialGradient(p.x,p.y,0,p.x,p.y,22);g.addColorStop(0,'#9de4c438');g.addColorStop(1,'#9de4c400');c.fillStyle=g;c.beginPath();c.arc(p.x,p.y,22,0,Math.PI*2);c.fill();c.strokeStyle='#97dfbe77';c.lineWidth=.7;c.beginPath();c.arc(p.x,p.y,radius+4,0,Math.PI*2);c.stroke();}
      c.fillStyle=connected||visited||selected?'#b6f1d0':colors[n.type]||'#9daaba';
      c.beginPath();c.arc(p.x,p.y,radius*(hovered?1.5:1),0,Math.PI*2);c.fill();c.globalAlpha=1;
    }
    const labelled=interactive?[...neighbors].map(id=>this.byId.get(id)).sort((a,b)=>Number(seeds.has(b.id))-Number(seeds.has(a.id))||b.degree-a.degree).slice(0,10):this.focused?[...this.sceneIds].map(id=>this.byId.get(id)):[];
    if(this.selected&&!labelled.some(n=>n.id===this.selected))labelled.push(this.byId.get(this.selected));
    this.drawNodeNames(pts,labelled);
    for(const n of labelled){const p=pts.get(n.id);if(p.x<8||p.x>w-8||p.y<8||p.y>h-40)continue;this.label(n,p,this.visited.has(n.id)||n.id===this.selected);}
    this.drawMap();
    this.positionTooltip();
  }
  label(n,p,visited) {
    const c=this.ctx;const name=n.name.replace('고용보험법 시행령 부칙 ','시행령 부칙 ').replace('고용보험법 시행령 ','시행령 ').replace('고용보험법 ','법 ');
    const lines=name.length>18?[name.slice(0,16),name.slice(16)]:[name];
    c.font='9px "Malgun Gothic",sans-serif';const width=Math.max(...lines.map(l=>c.measureText(l).width))+12;
    const x=Math.max(5,Math.min(this.width-width-5,p.x-width/2)),y=p.y+11;
    c.fillStyle=visited?'#172a22ec':'#111b24dd';c.strokeStyle=visited?'#385848':'#273b47';c.lineWidth=.6;
    c.beginPath();c.roundRect(x,y,width,lines.length*13+8,4);c.fill();c.stroke();c.fillStyle=visited?'#c0e4d0':'#8c9eae';c.textAlign='center';
    lines.forEach((line,i)=>c.fillText(line,x+width/2,y+13+i*13));
  }
  drawNodeNames(pts,priority) {
    const threshold=Math.max(.24,fitCamera(this.bounds,this.width,this.height).k*1.7);
    if(this.camera.k<=threshold)return;
    const c=this.ctx,occupied=[],excluded=new Set(priority.map(n=>n.id));
    const nameOf=n=>n.name.replace('고용보험법 시행령 ','시행령 ').replace('고용보험법 ','법 ');
    c.font='10px "Malgun Gothic",sans-serif';
    for(const n of priority){
      const p=pts.get(n.id),width=Math.min(180,c.measureText(nameOf(n)).width+12);
      occupied.push({left:p.x-width/2,right:p.x+width/2,top:p.y+8,bottom:p.y+45});
    }
    const candidates=this.nodes.filter(n=>{
      const p=pts.get(n.id);return !excluded.has(n.id)&&p.x>10&&p.x<this.width-10&&p.y>10&&p.y<this.height-30;
    }).sort((a,b)=>b.degree-a.degree||a.id.localeCompare(b.id));
    c.textAlign='center';c.lineJoin='round';c.lineWidth=3;
    c.strokeStyle='#0b131af0';c.fillStyle='#acbec9';
    c.globalAlpha=Math.min(1,(this.camera.k-threshold)/.14)*(this.focused ? .65 : 1);
    for(const n of candidates){
      const p=pts.get(n.id),full=nameOf(n),name=full.length>25?full.slice(0,24)+'…':full;
      const width=c.measureText(name).width+10;
      const box={left:p.x-width/2,right:p.x+width/2,top:p.y+9,bottom:p.y+26};
      if(box.left<5||box.right>this.width-5||occupied.some(b=>box.left<b.right&&box.right>b.left&&box.top<b.bottom&&box.bottom>b.top))continue;
      occupied.push(box);c.strokeText(name,p.x,p.y+21);c.fillText(name,p.x,p.y+21);
    }
    c.globalAlpha=1;
  }
  drawMap() {
    if(!this.focused)return;const c=this.mini.getContext('2d'),w=120,h=80;c.clearRect(0,0,w,h);
    const k=.065;for(const n of this.nodes){c.fillStyle=this.visited.has(n.id)?'#b3edca':'#647986';c.globalAlpha=this.visited.has(n.id)?1:.4;c.fillRect(n.x*k+w/2,n.y*k+h/2,1,1);}c.globalAlpha=1;
    c.strokeStyle='#94d6b7';c.lineWidth=.7;const vw=this.width/this.camera.k*k,vh=this.height/this.camera.k*k;
    c.strokeRect(this.camera.x*k+w/2-vw/2,this.camera.y*k+h/2-vh/2,vw,vh);
  }
  animate() {
    if(!this.reducedMotion&&this.activatedAt&&performance.now()-this.activatedAt<650)this.dirty=true;
    const dx=this.target.x-this.camera.x,dy=this.target.y-this.camera.y,dk=this.target.k-this.camera.k;
    const moving=Math.abs(dx)+Math.abs(dy)+Math.abs(dk)*100>.03;
    if(moving){const amount=this.reducedMotion?1:.16;this.camera.x+=dx*amount;this.camera.y+=dy*amount;this.camera.k+=dk*amount;
      this.camera=constrainCamera(this.camera,this.bounds,this.width,this.height);}
    if(moving||this.dirty){this.draw();this.dirty=false;}
    this.raf=requestAnimationFrame(()=>this.animate());
  }
}
