export type WorkerMessageType =
  | 'init'
  | 'convert'
  | 'progress'
  | 'log'
  | 'error'
  | 'file'
  | 'complete';

export type WorkerMessage<T = unknown> = {
  type: WorkerMessageType;
  payload: T;
};

export function encodeMessage<T>(type: WorkerMessageType, payload: T): WorkerMessage<T> {
  return { type, payload };
}
