import { encodeMessage } from '../worker-protocol';

test('encodeMessage builds init payload', () => {
  const msg = encodeMessage('init', { pyodideUrl: 'x' });
  expect(msg.type).toBe('init');
});
