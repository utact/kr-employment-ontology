import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {graphBounds,fitCamera,constrainCamera} from './graph.js';
import {panelWidths} from './layout.js';
import {capturedFrameIndex} from './playback.js';

const {nodes}=JSON.parse(readFileSync(new URL('./data/vault.json',import.meta.url),'utf8'));
const bounds=graphBounds(nodes);
const {responses}=JSON.parse(readFileSync(new URL('./data/baseline-responses.json',import.meta.url),'utf8'));

test('상담 표시가 실측 시각보다 먼저 나오지 않고 지연 후에도 기록을 따라잡는다',()=>{
  for(const {frames,durationMs} of responses){
    assert.equal(capturedFrameIndex(frames,0),-1);
    assert.equal(capturedFrameIndex(frames,frames[0].atMs-1),-1);
    for(let i=0;i<frames.length;i++)assert.equal(capturedFrameIndex(frames,frames[i].atMs),i);
    assert.equal(capturedFrameIndex(frames,durationMs+5000),frames.length-1);
    for(let elapsed=0;elapsed<durationMs;elapsed+=137){
      const index=capturedFrameIndex(frames,elapsed);
      if(index>=0)assert.ok(frames[index].atMs<=elapsed);
      if(index+1<frames.length)assert.ok(frames[index+1].atMs>elapsed);
    }
  }
});

test('전체 보기는 좁은 패널에서도 모든 실제 노드를 담는다',()=>{
  for(const [width,height] of [[320,280],[780,580],[1450,680]]){
    const camera=fitCamera(bounds,width,height);
    for(const node of nodes){
      const x=(node.x-camera.x)*camera.k+width/2;
      const y=(node.y-camera.y)*camera.k+height/2;
      assert.ok(x>=27.9&&x<=width-27.9);
      assert.ok(y>=47.9&&y<=height-47.9);
    }
  }
});

test('계속 축소하거나 밀어도 전체 보기보다 멀어지지 않는다',()=>{
  const width=800,height=600,fit=fitCamera(bounds,width,height);
  let camera=fit;
  for(let i=0;i<100;i++)camera=constrainCamera({x:camera.x+10000,y:camera.y-10000,k:camera.k*.5},bounds,width,height);
  assert.deepEqual(camera,fit);
});

test('확대 후 네 방향의 이동은 그래프 경계에서 멈춘다',()=>{
  const width=800,height=600;
  for(const x of [-1e9,1e9])for(const y of [-1e9,1e9]){
    const camera=constrainCamera({x,y,k:500},bounds,width,height);
    assert.equal(camera.k,5);
    assert.ok(camera.x-width/(2*camera.k)>=bounds.minX-48/camera.k-1e-8);
    assert.ok(camera.x+width/(2*camera.k)<=bounds.maxX+48/camera.k+1e-8);
    assert.ok(camera.y-height/(2*camera.k)>=bounds.minY-48/camera.k-1e-8);
    assert.ok(camera.y+height/(2*camera.k)<=bounds.maxY+48/camera.k+1e-8);
    assert.deepEqual(constrainCamera(camera,bounds,width,height),camera);
  }
});

test('패널을 넓혀도 최소 배율과 이동 제한이 다시 계산된다',()=>{
  const narrow=fitCamera(bounds,320,600);
  const wider=constrainCamera({...narrow,x:-1e8},bounds,1400,600);
  assert.ok(wider.k>=fitCamera(bounds,1400,600).k);
  assert.ok(Number.isFinite(wider.x)&&Number.isFinite(wider.y));
});

test('최대 확대에서 빈 모서리로 이동해도 실제 노드가 화면에 남는다',()=>{
  for(const x of [-1e9,1e9])for(const y of [-1e9,1e9]){
    const camera=constrainCamera({x,y,k:5},bounds,320,400,nodes);
    assert.ok(nodes.some(n=>Math.abs(n.x-camera.x)*camera.k<148&&Math.abs(n.y-camera.y)*camera.k<188));
  }
});

test('저장된 넓은 패널도 좁은 창에서 그래프 공간을 남긴다',()=>{
  for(const width of [776,1000,1500]){
    const sizes=panelWidths(width,700,700);
    assert.ok(sizes.left>=200&&sizes.right>=200);
    assert.ok(sizes.graph>=320-1e-8);
    assert.ok(Math.abs(sizes.left+sizes.right+sizes.graph+20-width)<1e-8);
  }
});

test('한쪽만 넓어진 설정과 기본 비율을 유지한다',()=>{
  const sizes=panelWidths(1500,500,250);
  assert.equal(sizes.left,500);assert.equal(sizes.right,250);assert.equal(sizes.graph,730);
  const small=panelWidths(776,20,20);
  assert.equal(small.left,200);assert.equal(small.right,200);assert.equal(small.graph,356);
});
