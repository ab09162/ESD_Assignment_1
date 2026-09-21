import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';
import { settings, request } from './common.js';
export { setup, handleSummary } from './common.js';

const winners = new Counter('booking_winners');
const rejected = new Counter('booking_rejected');
export const options = settings('concurrency', {
  vus: 1, iterations: 1, batch: 20, batchPerHost: 20,
  thresholds: { checks: ['rate==1'], booking_winners: ['count==1'], booking_rejected: ['count==19'] },
});

export default function (data) {
  const base = __ENV.BASE_URL || 'http://localhost:8000';
  const slot = { room_id: 3, start_time: new Date(data.baseTime).toISOString(),
    end_time: new Date(data.baseTime + 3600000).toISOString() };
  const responses = http.batch(Array.from({ length: 20 }, () => ({
    method: 'POST', url: `${base}/bookings`, body: JSON.stringify(slot),
    params: { headers: { 'Content-Type': 'application/json' }, timeout: '15s',
      tags: { name: '/bookings/concurrent' }, responseCallback: http.expectedStatuses(201, 409) },
  })));
  const successful = responses.filter((r) => r.status === 201);
  const conflicts = responses.filter((r) => r.status === 409);
  winners.add(successful.length);
  rejected.add(conflicts.length);
  check(responses, {
    'exactly one winner': () => successful.length === 1,
    'nineteen clean conflicts': () => conflicts.length === 19,
  });
  successful.forEach((r) => request('DELETE', `/bookings/${r.json('id')}`, null, '/bookings/{booking_id}'));
}
