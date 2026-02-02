import { zipStream } from '../zip';

test('zipStream appends files', () => {
  const z = zipStream();
  z.addFile('a.txt', new Uint8Array([1, 2]));
  expect(z.count()).toBe(1);
});
