import flow, { settings } from './common.js';
export { setup, handleSummary } from './common.js';
export const options = settings('stress', {
  stages: [
    { duration: '1m', target: 50 }, { duration: '2m', target: 100 },
    { duration: '2m', target: 200 }, { duration: '1m', target: 0 },
  ],
  thresholds: { unexpected_responses: ['rate<0.05'], http_req_duration: ['p(99)<5000'] },
});
export default flow;
