const dot = document.querySelector('#connection-dot');
const title = document.querySelector('#connection-title');
const note = document.querySelector('#connection-note');

async function refreshStatus() {
  title.textContent = 'Checking API';
  note.textContent = 'Process availability only';
  dot.classList.remove('is-up', 'is-down');
  try {
    const response = await fetch('/health', { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('API unavailable');
    dot.classList.add('is-up');
    title.textContent = 'API process online';
    note.textContent = 'Dependency readiness is not checked';
  } catch {
    dot.classList.add('is-down');
    title.textContent = 'API not detected';
    note.textContent = 'Interface preview only';
  }
}

document.querySelector('#refresh-status').addEventListener('click', refreshStatus);
const dialog = document.querySelector('#about-dialog');
document.querySelector('#about-button').addEventListener('click', () => dialog.showModal());
dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
refreshStatus();
