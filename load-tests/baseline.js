import flow, { settings } from './common.js';
export { setup, handleSummary } from './common.js';
export const options = settings('baseline', { vus: 10, duration: __ENV.DURATION || '2m' });
export default flow;
