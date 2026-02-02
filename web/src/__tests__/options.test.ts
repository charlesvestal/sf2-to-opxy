import { buildOptions } from '../options';

test('buildOptions maps defaults', () => {
  const opts = buildOptions({});
  expect(opts.velocities).toEqual([101]);
  expect(opts.resampleRate).toBe(22050);
});
