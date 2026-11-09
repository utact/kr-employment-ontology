export const INTRO_DURATION_MS=2180;
export const STARTUP_TIMEOUT_MS=12000;

export function canReveal(elapsed,{ready=false,failed=false,compact=false,reduced=false}={}) {
  const minimum=reduced?0:compact?560:INTRO_DURATION_MS;
  return failed||elapsed>=STARTUP_TIMEOUT_MS||(ready&&elapsed>=minimum);
}
