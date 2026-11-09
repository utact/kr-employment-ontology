// A bounded, deterministic scenario. No simulated LLM calls or invented timings.
export function runScenario(data, separationDate, clock = () => performance.now()) {
  const started = clock();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(separationDate) ||
      !Number.isFinite(Date.parse(separationDate)) ||
      new Date(`${separationDate}T00:00:00Z`).toISOString().slice(0, 10) !== separationDate) {
    throw new Error('올바른 이직일을 입력해 주세요.');
  }
  const config = data.scenario;
  if (separationDate < config.minDate || separationDate > config.maxDate) {
    throw new Error(`이 데모는 ${config.minDate}부터 볼트 기준일 ${config.maxDate}까지의 이직일을 다룹니다.`);
  }
  const byId = new Map(data.nodes.map(node => [node.id, node]));
  const visited = new Set();
  const events = [];
  const s = data.scene;
  function record(title, detail, ids, evidenceKeys = [], extra = {}) {
    for (const id of ids) {
      if (!byId.has(id)) throw new Error(`볼트에서 근거 노드를 찾지 못했습니다: ${id}`);
      visited.add(id);
    }
    for (const key of evidenceKeys) {
      if (!data.evidence[key]?.text) throw new Error(`근거가 누락되었습니다: ${key}`);
    }
    events.push({index: events.length, title, detail, nodeIds: ids, evidenceKeys,
      elapsedMs: +(clock() - started).toFixed(3), ...extra});
  }
  record('조건 확인', `${separationDate} 이직 · 일용근로자 · 1일 8시간`,
    [s.worker, s.date, s.result]);
  record('적용 조건', config.criterion,
    [s.workerRule, s.condition, s.date]);
  const current = separationDate >= config.threshold;
  record('시행일·경과조치', current
    ? `${config.threshold} 이후 이직 → 개정 규정`
    : `${config.threshold} 전 이직 → 종전 규정`,
    [s.condition, s.transition], ['effective', 'transition'],
    {operation: 'date-condition', input: separationDate, threshold: config.threshold, passed: current});
  const selectedEvidence = current ? 'current' : 'previous';
  const baseCap = current ? config.currentBaseCap : config.previousBaseCap;
  record('법령 버전 선택', `제68조 · 기초일액 상한 ${baseCap.toLocaleString('ko-KR')}원`,
    [s.cap, s.transition], [selectedEvidence],
    {operation: 'version-selection', selectedEvidence, excludedEvidence: current ? 'previous' : 'current', baseCap});
  const cap = Math.round(baseCap * config.rate);
  record('상한액 계산', `${baseCap.toLocaleString('ko-KR')}원 × ${config.rate * 100}% = ${cap.toLocaleString('ko-KR')}원`,
    [s.cap, s.rate, s.rule, s.result], [selectedEvidence, 'rate'],
    {operation: 'multiply', inputs: {baseCap, rate: config.rate}, result: cap});
  record('답변 근거', '상한액 · 지급 비율 · 경과조치',
    [s.cap, s.rate, s.transition, s.result, s.rule], [selectedEvidence, 'rate', 'transition', 'effective'],
    {operation: 'evidence-selection', cap});
  const durationMs = +(clock() - started).toFixed(3);
  return {scenarioId: config.id, separationDate, current, baseCap, rate: config.rate, cap,
    selectedEvidence, events, durationMs, visitedIds: [...visited],
    provenance: {vaultAsOf: data.meta.asOf, vaultFingerprint: data.meta.fingerprint},
    execution: 'deterministic-scenario', llmUsed: false,
    timingDefinition: 'Local rule execution only; excludes playback, network, and model generation.'};
}
