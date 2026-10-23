// k6 load test for the agent runtime, with pass/fail thresholds taken from the SLOs.
//
//   k6 run k6/agent-load.js                              # steady + spike
//   k6 run -e SCENARIO=soak -e BASE_URL=http://agent:8000 k6/agent-load.js
//   k6 run --summary-export=summary.json k6/agent-load.js  # feeds resilience/capacity.py
//
// Agent requests are slow (multiple model calls) and expensive, so the tests use
// arrival-rate executors: load stays constant even when the system slows down,
// which is what real users do, and what exposes queueing.
import http from 'k6/http';
import { check } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const RPS = Number(__ENV.RPS || 1);

const agentSuccess = new Rate('agent_success');           // outcome == "success"
const agentPlatformError = new Rate('agent_platform_error'); // outcomes that burn the SLO
const agentSteps = new Trend('agent_steps');
const agentCost = new Trend('agent_cost_usd');
const outcomes = new Counter('agent_outcomes');

const QUESTIONS = [
  'Is payments-api healthy right now?',
  'Which incident is open for doc-ingest?',
  'Can we ship a feature to auth-service today based on its error budget?',
  'Which runbook should I follow for high p95 latency?',
  'How many minutes of downtime does a 99.5% availability SLO allow over 28 days?',
  'Is payments-api degraded, and does it still have enough error budget to ship a feature?',
];

const scenarios = {
  steady: {
    executor: 'constant-arrival-rate', rate: RPS, timeUnit: '1s', duration: '5m',
    preAllocatedVUs: 20, maxVUs: 100,
  },
  spike: {
    executor: 'ramping-arrival-rate', startRate: RPS, timeUnit: '1s',
    preAllocatedVUs: 20, maxVUs: 200,
    stages: [
      { target: RPS * 5, duration: '30s' },  // 5x spike
      { target: RPS * 5, duration: '2m' },
      { target: RPS, duration: '30s' },      // recovery: watch latency come back
    ],
  },
  soak: {
    executor: 'constant-arrival-rate', rate: RPS, timeUnit: '1s', duration: '2h',
    preAllocatedVUs: 20, maxVUs: 100,
  },
};

const selected = (__ENV.SCENARIO || 'steady,spike').split(',');
// Spike after the steady phase when both run, so the spike starts from a warm, steady system.
if (selected.includes('steady') && selected.includes('spike')) scenarios.spike.startTime = '5m';

export const options = {
  scenarios: Object.fromEntries(Object.entries(scenarios).filter(([k]) => selected.includes(k))),
  thresholds: {
    // availability SLO 99% -> fail the test if platform errors exceed 1%
    agent_platform_error: ['rate<0.01'],
    http_req_failed: ['rate<0.01'],
    // latency SLO for the incident-desk agent on CPU-sized models
    'http_req_duration{endpoint:run}': ['p(95)<20000', 'p(99)<40000'],
    // runaway behaviour: steps and cost per run must stay bounded under load
    agent_steps: ['p(95)<=6'],
    agent_cost_usd: ['p(95)<0.01'],
    // abort early if the system is clearly falling over
    agent_success: [{ threshold: 'rate>0.80', abortOnFail: true, delayAbortEval: '1m' }],
  },
};

export default function () {
  const question = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(`${BASE_URL}/run`, JSON.stringify({ question }), {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'run' },
    timeout: '90s',
  });
  const ok = check(res, { 'status 200': (r) => r.status === 200 });
  if (!ok) {
    agentPlatformError.add(1);
    agentSuccess.add(0);
    return;
  }
  const body = res.json();
  outcomes.add(1, { outcome: body.outcome });
  agentSuccess.add(body.outcome === 'success');
  agentPlatformError.add(['llm_unavailable', 'deadline', 'invalid_output'].includes(body.outcome));
  agentSteps.add(body.steps);
  agentCost.add(body.cost_usd);
}
