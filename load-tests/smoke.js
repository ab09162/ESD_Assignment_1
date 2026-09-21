import flow, { settings } from './common.js';
export { setup, handleSummary } from './common.js';
export const options = settings('smoke', { vus: 1, iterations: 5 });
export default flow;
