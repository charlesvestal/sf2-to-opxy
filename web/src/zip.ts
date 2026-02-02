import { Zip, ZipPassThrough } from 'fflate';

export type ZipStream = {
  addFile: (name: string, data: Uint8Array) => void;
  count: () => number;
  onData: (handler: (chunk: Uint8Array, final: boolean) => void) => void;
  finalize: () => void;
};

export function zipStream(): ZipStream {
  let entries = 0;
  let handler: ((chunk: Uint8Array, final: boolean) => void) | null = null;
  const zip = new Zip((err, data, final) => {
    if (err) {
      throw err;
    }
    if (handler) {
      handler(data, !!final);
    }
  });

  return {
    addFile(name: string, data: Uint8Array) {
      const file = new ZipPassThrough(name);
      zip.add(file);
      file.push(data, true);
      entries += 1;
    },
    count() {
      return entries;
    },
    onData(cb: (chunk: Uint8Array, final: boolean) => void) {
      handler = cb;
    },
    finalize() {
      zip.end();
    }
  };
}
