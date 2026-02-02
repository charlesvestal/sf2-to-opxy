import { encodeMessage } from './worker-protocol';

const DEFAULT_PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.mjs';
const DEFAULT_PYODIDE_INDEX = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/';

let pyodide: any = null;
let pyReady = false;

async function ensurePyodide(payload: { pyodideUrl?: string; indexUrl?: string; pyBaseUrl?: string }) {
  if (pyReady) return;
  postMessage(encodeMessage('progress', { stage: 'pyodide:load' }));
  const pyodideUrl = payload.pyodideUrl ?? DEFAULT_PYODIDE_URL;
  const indexUrl = payload.indexUrl ?? DEFAULT_PYODIDE_INDEX;
  const { loadPyodide } = await import(/* @vite-ignore */ pyodideUrl);
  pyodide = await loadPyodide({ indexURL: indexUrl });

  postMessage(encodeMessage('progress', { stage: 'pyodide:micropip' }));
  await pyodide.loadPackage('micropip');
  await pyodide.runPythonAsync(
    "import micropip\nawait micropip.install('sf2utils')"
  );

  postMessage(encodeMessage('progress', { stage: 'pyodide:load-py' }));
  const pyBaseUrl = payload.pyBaseUrl ?? '/py';
  const manifestUrl = new URL(`${pyBaseUrl.replace(/\/$/, '')}/manifest.json`, self.location.href).toString();
  const manifestRes = await fetch(manifestUrl);
  const manifest = await manifestRes.json();
  const files: string[] = manifest.files ?? [];

  pyodide.FS.mkdirTree('/py');
  for (const relPath of files) {
    const url = new URL(`${pyBaseUrl.replace(/\/$/, '')}/${relPath}`, self.location.href).toString();
    const res = await fetch(url);
    const text = await res.text();
    const destPath = `/py/${relPath}`;
    pyodide.FS.mkdirTree(destPath.substring(0, destPath.lastIndexOf('/')));
    pyodide.FS.writeFile(destPath, text, { encoding: 'utf8' });
  }

  pyodide.runPython("import sys\nsys.path.insert(0, '/py')");
  pyReady = true;
  postMessage(encodeMessage('progress', { stage: 'pyodide:ready' }));
}

async function readOpfsFile(name: string): Promise<Uint8Array> {
  const root = await navigator.storage.getDirectory();
  const handle = await root.getFileHandle(name);
  const file = await handle.getFile();
  return new Uint8Array(await file.arrayBuffer());
}

async function collectFiles(root: string): Promise<{ path: string; data: Uint8Array }[]> {
  const out: { path: string; data: Uint8Array }[] = [];
  function walk(dir: string) {
    const entries = pyodide.FS.readdir(dir);
    for (const entry of entries) {
      if (entry === '.' || entry === '..') continue;
      const full = `${dir}/${entry}`;
      const stat = pyodide.FS.stat(full);
      if (pyodide.FS.isDir(stat.mode)) {
        walk(full);
      } else {
        const data = pyodide.FS.readFile(full) as Uint8Array;
        out.push({ path: full.replace(root + '/', ''), data });
      }
    }
  }
  walk(root);
  return out;
}

self.onmessage = async (event: MessageEvent) => {
  const { type, payload } = event.data ?? {};
  try {
    if (type === 'init') {
      await ensurePyodide(payload ?? {});
      postMessage(encodeMessage('log', { message: 'Pyodide ready' }));
      return;
    }

    if (type === 'convert') {
      await ensurePyodide(payload ?? {});
      const options = payload?.options ?? {};
      const inputName = payload?.inputName ?? 'input.sf2';
      const outDir = payload?.outDir ?? '/work/out';

      let buffer: Uint8Array | null = null;
      if (payload?.opfsName) {
        postMessage(encodeMessage('progress', { stage: 'opfs:read' }));
        buffer = await readOpfsFile(payload.opfsName);
      } else if (payload?.fileBuffer) {
        buffer = new Uint8Array(payload.fileBuffer);
      }

      if (!buffer) {
        throw new Error('No input file buffer provided');
      }

      pyodide.FS.mkdirTree('/work');
      pyodide.FS.writeFile(`/work/${inputName}`, buffer);

      postMessage(encodeMessage('progress', { stage: 'pyodide:convert' }));
      const optionsJson = JSON.stringify(options ?? {});
      pyodide.runPython(
        `from web_entry import run_conversion\nrun_conversion('/work/${inputName}', '${outDir}', '''${optionsJson}''')`
      );

      postMessage(encodeMessage('progress', { stage: 'pyodide:collect' }));
      const files = await collectFiles(outDir);
      for (const file of files) {
        postMessage(encodeMessage('file', file), [file.data.buffer]);
      }

      postMessage(encodeMessage('complete', { count: files.length }));
    }
  } catch (err: any) {
    postMessage(
      encodeMessage('error', {
        message: err?.message ?? String(err),
        stack: err?.stack ?? null
      })
    );
  }
};
