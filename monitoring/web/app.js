let token;
const el = id => document.getElementById(id);
function render(state) {
  el('connection').textContent = state.online ? 'Controller connected' : state.broker ? 'Broker connected · waiting for controller' : 'Broker offline';
  el('mode').textContent = state.online ? (state.armed ? 'Armed' : 'Disarmed') : 'Offline · disarmed';
  el('output').textContent = state.keyboard_enabled ? 'Keyboard output enabled' : 'Dry run · no keys will be sent';
  el('pending').textContent = state.pending ? 'Waiting for device acknowledgement…' : '';
  el('arm').disabled = el('disarm').disabled = !state.online;
  el('empty').hidden = state.history.length > 0;
  el('history').replaceChildren(...state.history.map(item => {
    const row = document.createElement('li');
    for (const text of [item.time, item.gesture.replaceAll('_', ' '), item.outcome + (item.key ? ` · ${item.key}` : '')]) {
      const span = document.createElement('span'); span.textContent = text; row.append(span);
    }
    return row;
  }));
}
async function post(path, body) {
  try {
    const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json', 'X-MotionCue-Token':token}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    el('error').textContent = ''; render(data);
  } catch (error) { el('error').textContent = error.message; }
}
async function start() {
  const state = await (await fetch('/api/state')).json(); token = state.token;
  for (const gesture of ['swipe_left','swipe_right']) {
    for (const key of state.keys) el(gesture).add(new Option(key, key));
    el(gesture).value = state.mappings[gesture];
  }
  render(state);
  const stream = new EventSource('/api/stream');
  stream.onmessage = event => { render(JSON.parse(event.data)); el('error').textContent = ''; };
  stream.onerror = () => { el('error').textContent = 'Host connection lost. Reconnecting…'; el('arm').disabled = el('disarm').disabled = true; el('mode').textContent = 'Host offline'; };
}
el('arm').onclick = () => post('/api/mode', {armed:true});
el('disarm').onclick = () => post('/api/mode', {armed:false});
el('save').onclick = () => post('/api/mappings', {swipe_left:el('swipe_left').value,swipe_right:el('swipe_right').value});
start().catch(error => { el('error').textContent = error.message; });
