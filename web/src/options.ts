export type UiOptions = Partial<{
  velocities: string;
  velocityMode: 'keep' | 'split';
  resampleRate: number;
  bitDepth: number;
  noResample: boolean;
  zeroCrossing: boolean;
  loopEndOffset: number;
  forceDrum: boolean;
  forceInstrument: boolean;
  instrumentPlaymode: 'auto' | 'poly' | 'mono' | 'legato';
  drumVelocityMode: 'closest' | 'strict';
}>;

export type BuildOptions = {
  velocities: number[];
  velocityMode: 'keep' | 'split';
  resampleRate: number;
  bitDepth: number;
  noResample: boolean;
  zeroCrossing: boolean;
  loopEndOffset: number;
  forceDrum: boolean;
  forceInstrument: boolean;
  instrumentPlaymode: 'auto' | 'poly' | 'mono' | 'legato';
  drumVelocityMode: 'closest' | 'strict';
};

const DEFAULTS: BuildOptions = {
  velocities: [101],
  velocityMode: 'keep',
  resampleRate: 22050,
  bitDepth: 16,
  noResample: false,
  zeroCrossing: false,
  loopEndOffset: 0,
  forceDrum: false,
  forceInstrument: false,
  instrumentPlaymode: 'auto',
  drumVelocityMode: 'closest'
};

function parseVelocities(value: string | undefined): number[] {
  if (!value) {
    return DEFAULTS.velocities;
  }
  const parsed = value
    .split(',')
    .map((item) => Number.parseInt(item.trim(), 10))
    .filter((item) => Number.isFinite(item) && item > 0 && item <= 127);
  return parsed.length ? parsed : DEFAULTS.velocities;
}

export function buildOptions(input: UiOptions): BuildOptions {
  return {
    velocities: parseVelocities(input.velocities),
    velocityMode: input.velocityMode ?? DEFAULTS.velocityMode,
    resampleRate: input.resampleRate ?? DEFAULTS.resampleRate,
    bitDepth: input.bitDepth ?? DEFAULTS.bitDepth,
    noResample: input.noResample ?? DEFAULTS.noResample,
    zeroCrossing: input.zeroCrossing ?? DEFAULTS.zeroCrossing,
    loopEndOffset: input.loopEndOffset ?? DEFAULTS.loopEndOffset,
    forceDrum: input.forceDrum ?? DEFAULTS.forceDrum,
    forceInstrument: input.forceInstrument ?? DEFAULTS.forceInstrument,
    instrumentPlaymode: input.instrumentPlaymode ?? DEFAULTS.instrumentPlaymode,
    drumVelocityMode: input.drumVelocityMode ?? DEFAULTS.drumVelocityMode
  };
}
