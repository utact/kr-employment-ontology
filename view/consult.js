const form = document.querySelector('#consult');
const status = document.querySelector('#status');
const result = document.querySelector('#result');

function showList(container, tag, texts) {
  container.replaceChildren(...texts.map(text => {
    const element = document.createElement(tag);
    element.textContent = text;
    return element;
  }));
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const question = form.elements.question.value;
  if (!question.trim()) return;
  const button = form.querySelector('button');
  button.disabled = true;
  result.hidden = true;
  status.textContent = '관련 근거를 찾고 답변을 검토하고 있습니다.';
  try {
    const asOf = form.elements.asOf.value;
    const input = asOf ? {question, asOf} : {question};
    const response = await fetch('./api/ask', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(input)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '상담 서버에 연결하지 못했습니다.');
    showList(document.querySelector('#answer'), 'p', data.answer.split(/\n\n/).filter(Boolean));
    showList(document.querySelector('#questions'), 'li', data.questions);
    const sources = document.querySelector('#sources');
    sources.hidden = !data.sources.length;
    sources.open = false;
    showList(sources.querySelector('ul'), 'li', data.sources.map(s =>
      [`[${s.key}] ${s.citation}${s.version ? ` · ${s.version} 시행` : ''}`, ...(s.quotes || [])].join('\n')));
    document.querySelector('#metadata').textContent = `상담일 ${data.asOf} · ${data.model}`;
    result.hidden = false;
    status.textContent = '';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
