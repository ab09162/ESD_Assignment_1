import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { Rate, Counter } from 'k6/metrics';

const base = __ENV.BASE_URL || 'http://localhost:8000';
export const unexpected = new Rate('unexpected_responses');
export const conflicts = new Counter('expected_conflicts');

export function settings(profile, extra = {}) {
  return {
    systemTags: ['status', 'method', 'name', 'scenario', 'expected_response'],
    tags: { profile, phase: __ENV.PHASE || 'manual' },
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)'],
    thresholds: {
      unexpected_responses: ['rate<0.01'],
      checks: ['rate>0.99'],
      http_req_duration: ['p(95)<1000', 'p(99)<2000'],
    },
    ...extra,
  };
}

export function setup() {
  const ready = http.get(`${base}/ready`, { tags: { name: '/ready' } });
  if (ready.status !== 200) throw new Error('Application not ready');
  // A shared base plus globally unique iteration index prevents VU collisions.
  return { baseTime: Date.now() + 24 * 60 * 60 * 1000 };
}

export function request(method, path, body, name, expected = 200) {
  const response = http.request(method, `${base}${path}`, body ? JSON.stringify(body) : null, {
    headers: { 'Content-Type': 'application/json' },
    tags: { name },
    responseCallback: http.expectedStatuses(expected),
    timeout: '15s',
  });
  const ok = check(response, { [`${method} ${name} is ${expected}`]: (r) => r.status === expected });
  unexpected.add(!ok);
  return response;
}

export default function flow(data) {
  const index = exec.scenario.iterationInTest;
  const start = data.baseTime + index * 60000;
  const slot = { room_id: 1 + index % 3, start_time: new Date(start).toISOString(),
    end_time: new Date(start + 60000).toISOString() };
  request('GET', '/rooms', null, '/rooms');
  request('GET', `/rooms/${slot.room_id}/availability?start_time=${encodeURIComponent(slot.start_time)}&end_time=${encodeURIComponent(slot.end_time)}`,
    null, '/rooms/{room_id}/availability');
  const created = request('POST', '/bookings', slot, '/bookings', 201);
  if (created.status === 201) {
    const id = created.json('id');
    try {
      request('GET', `/bookings/${id}`, null, '/bookings/{booking_id}');
      if (index % 5 === 0) {
        const conflict = request('POST', '/bookings', slot, '/bookings/conflict', 409);
        if (conflict.status === 409) conflicts.add(1);
      }
      if (index % 10 === 0) request('GET', '/bookings?limit=10', null, '/bookings');
    } finally {
      request('DELETE', `/bookings/${id}`, null, '/bookings/{booking_id}');
    }
  }
  sleep(0.2);
}

export function handleSummary(data) {
  const output = __ENV.SUMMARY_FILE || '/results/last-run.json';
  const values = (metric) => data.metrics[metric] ? data.metrics[metric].values : {};
  return {
    [output]: JSON.stringify(data, null, 2),
    stdout: JSON.stringify({
      profile: __ENV.PHASE || 'manual', http_reqs: values('http_reqs'),
      http_req_duration: values('http_req_duration'),
      unexpected_responses: values('unexpected_responses'), checks: values('checks'),
      expected_conflicts: values('expected_conflicts'),
    }, null, 2) + '\n',
  };
}
