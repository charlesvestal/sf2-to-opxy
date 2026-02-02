import { encodeMessage } from './worker-protocol';

const status = document.getElementById('status');

function setStatus(text: string) {
  if (status) status.textContent = text;
}

const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
worker.onmessage = (event) => {
  const { type, payload } = event.data ?? {};
  if (type === 'progress') {
    setStatus(`Progress: ${payload.stage}`);
  } else if (type === 'error') {
    setStatus(`Error: ${payload.message}`);
  } else if (type === 'complete') {
    setStatus(`Complete: ${payload.count} files`);
  }
};

const baseUrl = import.meta.env.BASE_URL;
worker.postMessage(
  encodeMessage('init', {
    pyBaseUrl: `${baseUrl}py`,
    pyodideUrl: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.mjs',
    indexUrl: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/'
  })
);

setStatus('Loading Pyodide...');
