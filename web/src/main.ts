import { buildOptions } from './options';
import { encodeMessage } from './worker-protocol';
import { zipStream } from './zip';

const status = document.getElementById('status');
const logEl = document.getElementById('log');
const downloadEl = document.getElementById('download');
const fileInput = document.getElementById('sf2-file') as HTMLInputElement | null;
const convertBtn = document.getElementById('convert-btn') as HTMLButtonElement | null;

function setStatus(text: string) {
  if (status) status.textContent = text;
}

function appendLog(text: string) {
  if (!logEl) return;
  logEl.textContent = `${logEl.textContent ?? ''}${text}\n`;
}

const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });

worker.onmessage = (event) => {
  const { type, payload } = event.data ?? {};
  if (type === 'progress') {
    setStatus(`Progress: ${payload.stage}`);
  } else if (type === 'log') {
    appendLog(payload.message ?? '');
  } else if (type === 'error') {
    setStatus(`Error: ${payload.message}`);
    if (payload.stack) appendLog(payload.stack);
    if (convertBtn) convertBtn.disabled = false;
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

async function storeInOpfs(file: File): Promise<string | null> {
  if (!('storage' in navigator) || !(navigator.storage as any).getDirectory) {
    return null;
  }
  const root = await (navigator.storage as any).getDirectory();
  const handle = await root.getFileHandle(file.name, { create: true });
  const writable = await handle.createWritable();
  await writable.write(file);
  await writable.close();
  return file.name;
}

function readOptionsFromUi() {
  const velocities = (document.getElementById('velocities') as HTMLInputElement | null)?.value;
  const velocityMode = (document.getElementById('velocity-mode') as HTMLSelectElement | null)?.value as
    | 'keep'
    | 'split'
    | undefined;
  const resampleRate = Number((document.getElementById('resample-rate') as HTMLInputElement | null)?.value);
  const bitDepth = Number((document.getElementById('bit-depth') as HTMLInputElement | null)?.value);
  const noResample = (document.getElementById('no-resample') as HTMLInputElement | null)?.checked;
  const zeroCrossing = (document.getElementById('zero-crossing') as HTMLInputElement | null)?.checked;
  const loopEndOffset = Number((document.getElementById('loop-end-offset') as HTMLInputElement | null)?.value);
  const forceDrum = (document.getElementById('force-drum') as HTMLInputElement | null)?.checked;
  const forceInstrument = (document.getElementById('force-instrument') as HTMLInputElement | null)?.checked;
  const instrumentPlaymode = (document.getElementById('instrument-playmode') as HTMLSelectElement | null)?.value as
    | 'auto'
    | 'poly'
    | 'mono'
    | 'legato'
    | undefined;
  const drumVelocityMode = (document.getElementById('drum-velocity-mode') as HTMLSelectElement | null)?.value as
    | 'closest'
    | 'strict'
    | undefined;

  return buildOptions({
    velocities,
    velocityMode,
    resampleRate,
    bitDepth,
    noResample,
    zeroCrossing,
    loopEndOffset,
    forceDrum,
    forceInstrument,
    instrumentPlaymode,
    drumVelocityMode
  });
}

async function convert() {
  if (!fileInput?.files?.length) {
    setStatus('Select a .sf2 file first.');
    return;
  }

  if (convertBtn) convertBtn.disabled = true;
  if (downloadEl) downloadEl.innerHTML = '';
  if (logEl) logEl.textContent = '';

  const file = fileInput.files[0];
  const options = readOptionsFromUi();
  const zip = zipStream();
  const chunks: Uint8Array[] = [];

  zip.onData((chunk, final) => {
    chunks.push(chunk);
    if (final && downloadEl) {
      const blob = new Blob(chunks, { type: 'application/zip' });
      const url = URL.createObjectURL(blob);
      downloadEl.innerHTML = '';
      const link = document.createElement('a');
      link.href = url;
      link.download = `${file.name.replace(/\.sf2$/i, '')}_opxy.zip`;
      link.textContent = 'Download conversion ZIP';
      downloadEl.appendChild(link);
      setStatus('Done');
      if (convertBtn) convertBtn.disabled = false;
    }
  });

  worker.onmessage = (event) => {
    const { type, payload } = event.data ?? {};
    if (type === 'progress') {
      if (typeof payload?.current === 'number' && typeof payload?.total === 'number') {
        setStatus(`Converted ${payload.current} / ${payload.total} presets`);
      } else {
        setStatus(`Progress: ${payload.stage}`);
      }
    } else if (type === 'log') {
      appendLog(payload.message ?? '');
    } else if (type === 'file') {
      zip.addFile(payload.path, payload.data);
    } else if (type === 'complete') {
      zip.finalize();
    } else if (type === 'error') {
      setStatus(`Error: ${payload.message}`);
      if (payload.stack) appendLog(payload.stack);
      if (convertBtn) convertBtn.disabled = false;
    }
  };

  const payload: Record<string, unknown> = {
    options,
    inputName: file.name,
    outDir: '/work/out'
  };

  try {
    const opfsName = await storeInOpfs(file);
    if (opfsName) {
      payload.opfsName = opfsName;
    } else {
      const buffer = await file.arrayBuffer();
      payload.fileBuffer = buffer;
    }
  } catch (err) {
    appendLog(`OPFS unavailable: ${String(err)}`);
    const buffer = await file.arrayBuffer();
    payload.fileBuffer = buffer;
  }

  const transferables = payload.fileBuffer ? [payload.fileBuffer as ArrayBuffer] : [];
  worker.postMessage(encodeMessage('convert', payload), transferables);
}

convertBtn?.addEventListener('click', () => {
  convert().catch((err) => {
    setStatus(`Error: ${String(err)}`);
    if (convertBtn) convertBtn.disabled = false;
  });
});
