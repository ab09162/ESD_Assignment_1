import flow, { settings } from './common.js';
export { setup, handleSummary } from './common.js';
export const options = settings('load', {
  stages: [
    { duration: '30s', target: 10 }, { duration: '2m', target: 10 },
    { duration: '30s', target: 25 }, { duration: '2m', target: 25 },
    { duration: '30s', target: 50 }, { duration: '2m', target: 50 },
    { duration: '30s', target: 100 }, { duration: '2m', target: 100 },
    { duration: '30s', target: 200 }, { duration: '2m', target: 200 },
    { duration: '30s', target: 0 },
  ],
});
export default flow;
