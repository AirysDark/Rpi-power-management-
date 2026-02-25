let lastFetchTime = 0;

// --------------------------------------------------
// helpers
// --------------------------------------------------

function healthClass(score) {
  if (score === 0) return 'offline';
  if (score < 50) return 'bad';
  if (score < 75) return 'warn';
  return 'good';
}

function healthLabel(score) {
  if (score === 0) return ['offline','OFFLINE'];
  if (score < 50) return ['bad','CRITICAL'];
  if (score < 75) return ['warn','WARN'];
  return ['good','OK'];
}

function formatUptime(sec) {
  if (!sec) return '-';
  sec = Math.floor(sec);

  const d = Math.floor(sec/86400);
  const h = Math.floor((sec%86400)/3600);
  const m = Math.floor((sec%3600)/60);

  if (d > 0) return `${d}d ${h}h`;
  return `${h}h ${m}m`;
}

function secondsAgo(ts) {
  if (!ts) return '-';

  const s = Math.floor((Date.now()/1000) - ts);

  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  return `${Math.floor(s/3600)}h ago`;
}

// --------------------------------------------------
// command sender
// --------------------------------------------------

async function sendCmd(btn, ip, cmd) {
  if (!ip) return;

  btn.classList.add('busy');
  btn.disabled = true;

  const old = btn.textContent;
  btn.textContent = '…';

  try {
    const payload = {
      ip,
      cmd,
      ts: Math.floor(Date.now()/1000)
    };

    const res = await fetch('/api/cmd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    btn.textContent = res.ok ? '✓' : 'ERR';

  } catch {
    btn.textContent = 'ERR';
  }

  setTimeout(() => {
    btn.textContent = old;
    btn.classList.remove('busy');
    btn.disabled = false;
  }, 1500);
}

// --------------------------------------------------
// loader
// --------------------------------------------------

async function loadFleet() {
  document.getElementById('refresh').textContent = 'refreshing…';

  try {
    const res = await fetch('/api/fleet', { cache: 'no-store' });
    if (!res.ok) throw new Error('bad response');

    const data = await res.json();
    lastFetchTime = Date.now()/1000;

    renderFleet(data);

    document.getElementById('refresh').textContent =
      'updated ' + new Date().toLocaleTimeString();

  } catch (err) {
    console.error(err);
    document.getElementById('summary').textContent =
      '⚠️ Fleet unreachable — retrying…';
    document.getElementById('refresh').textContent = 'error';
  }
}

// --------------------------------------------------
// renderer
// --------------------------------------------------

function renderFleet(data) {
  const grid = document.getElementById('grid');

  // worst-first sort
  data.sort((a,b) => {
    const sa = a.boot_health?.score ?? 0;
    const sb = b.boot_health?.score ?? 0;
    return sa - sb;
  });

  grid.innerHTML = '';

  let good=0, warn=0, bad=0, off=0;
  let scoreTotal = 0;

  data.forEach(d => {
    const score = d.boot_health?.score ?? 0;
    const cls = healthClass(score);
    const [badgeCls,label] = healthLabel(score);
    const offline = score === 0;

    if (cls==='good') good++;
    else if (cls==='warn') warn++;
    else if (cls==='bad') bad++;
    else off++;

    scoreTotal += score;

    const el = document.createElement('div');
    el.className = 'card ' + cls;

    el.innerHTML = `
      <h3>
        ${d.device?.device_id || 'unknown'}
        <span class="badge ${badgeCls}">${label}</span>
      </h3>

      <div>Role: ${d.device?.role || '-'}</div>
      <div>Site: ${d.device?.site || '-'}</div>
      <div>Health: <b>${score}</b></div>

      <div class="status small">
        Host: ${d.hostname || '-'}<br>
        Uptime: ${formatUptime(d.uptime_sec)}<br>
        Seen: ${secondsAgo(d.timestamp)}
      </div>

      <div class="cmds">
        <button ${offline?'disabled':''}
          onclick="sendCmd(this,'${d.ip}','reboot')">Reboot</button>
        <button ${offline?'disabled':''}
          onclick="sendCmd(this,'${d.ip}','shutdown')">Shutdown</button>
        <button ${offline?'disabled':''}
          onclick="sendCmd(this,'${d.ip}','update')">Update</button>
        <button ${offline?'disabled':''}
          onclick="sendCmd(this,'${d.ip}','rotate-key')">Rotate Key</button>
      </div>
    `;

    grid.appendChild(el);
  });

  document.getElementById('summary').textContent =
    `Nodes: ${data.length}  •  OK:${good}  WARN:${warn}  BAD:${bad}  OFFLINE:${off}`;

  const avg = data.length ? (scoreTotal / data.length) : 0;
  document.getElementById('healthBar').style.width = avg + '%';
}

// --------------------------------------------------

loadFleet();
setInterval(loadFleet, 5000);