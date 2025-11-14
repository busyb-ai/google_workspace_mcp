# Task 5.9: Performance and Load Testing

## Overview

This document provides comprehensive procedures for performance and load testing of the Google Workspace MCP service to establish baseline metrics and identify capacity limits.

## Objectives

1. Establish performance baseline for common operations
2. Determine service capacity (requests per second)
3. Identify resource utilization patterns
4. Test service behavior under load
5. Validate auto-scaling thresholds (if configured)
6. Document performance characteristics for capacity planning

---

## Test Environment

- **Service URL**: `http://google-workspace.busyb.local:8000`
- **ECS Configuration**:
  - CPU: 512 units (0.5 vCPU)
  - Memory: 1024 MB (1 GB)
  - Desired tasks: 1
- **Load Testing Tools**: k6, Apache Bench (ab), or hey
- **Monitoring**: CloudWatch metrics, ECS task metrics

---

## Prerequisites

- Service deployed and healthy
- OAuth credentials configured for test user
- CloudWatch dashboard ready for monitoring
- Load testing tool installed

---

## Test Tools Setup

### Option 1: k6 (Recommended)

```bash
# Install k6 (macOS)
brew install k6

# Verify installation
k6 version
```

### Option 2: Apache Bench (ab)

```bash
# Usually pre-installed on macOS/Linux
ab -V
```

### Option 3: hey

```bash
# Install hey
go install github.com/rakyll/hey@latest

# Or download binary
wget https://hey-release.s3.us-east-2.amazonaws.com/hey_darwin_amd64
chmod +x hey_darwin_amd64
sudo mv hey_darwin_amd64 /usr/local/bin/hey
```

---

## Performance Test Suite

### Test 1: Baseline Health Check Performance

**Objective**: Establish baseline response times for health endpoint

**k6 Test Script** (`health-check-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');

export let options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 concurrent users
    { duration: '1m', target: 5 },    // Stay at 5 users for 1 minute
    { duration: '30s', target: 10 },  // Ramp up to 10 users
    { duration: '1m', target: 10 },   // Stay at 10 users for 1 minute
    { duration: '30s', target: 20 },  // Ramp up to 20 users
    { duration: '1m', target: 20 },   // Stay at 20 users for 1 minute
    { duration: '30s', target: 0 },   // Ramp down to 0
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500', 'p(99)<1000'], // 95% under 500ms, 99% under 1s
    'errors': ['rate<0.1'], // Error rate < 10%
  },
};

export default function() {
  const url = 'http://google-workspace.busyb.local:8000/health';

  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    tags: { name: 'HealthCheck' },
  };

  const response = http.get(url, params);

  // Record response time
  responseTime.add(response.timings.duration);

  // Check response
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response has status field': (r) => JSON.parse(r.body).status === 'healthy',
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  errorRate.add(!success);

  sleep(1); // 1 second between requests per user
}
```

**Run Test**:

```bash
k6 run health-check-test.js
```

**Expected Results**:
- P95 response time: < 200ms
- P99 response time: < 500ms
- Error rate: 0%
- Throughput: > 50 requests/second

---

### Test 2: MCP Tool List Performance

**Objective**: Test MCP tools/list endpoint under load

**k6 Test Script** (`tools-list-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '2m', target: 10 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<1000'],
  },
};

export default function() {
  const url = 'http://google-workspace.busyb.local:8000/mcp';

  const payload = JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/list',
    params: {}
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const response = http.post(url, payload, params);

  check(response, {
    'status is 200': (r) => r.status === 200,
    'has tools list': (r) => JSON.parse(r.body).result && JSON.parse(r.body).result.tools,
  });

  sleep(2);
}
```

**Run Test**:

```bash
k6 run tools-list-test.js
```

---

### Test 3: Authenticated Gmail Operations

**Objective**: Test Gmail search under load (authenticated operations)

**k6 Test Script** (`gmail-search-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const TEST_EMAIL = 'test@gmail.com';

export let options = {
  stages: [
    { duration: '30s', target: 3 },
    { duration: '2m', target: 3 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<3000'], // Gmail API can be slower
  },
};

export default function() {
  const url = 'http://google-workspace.busyb.local:8000/mcp';

  const payload = JSON.stringify({
    jsonrpc: '2.0',
    id: 1,
    method: 'tools/call',
    params: {
      name: 'search_gmail_messages',
      arguments: {
        user_google_email: TEST_EMAIL,
        query: 'subject:test',
      }
    }
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const response = http.post(url, payload, params);

  check(response, {
    'status is 200': (r) => r.status === 200,
    'has result': (r) => {
      const body = JSON.parse(r.body);
      return body.result !== undefined;
    },
  });

  sleep(5); // Gmail API has rate limits
}
```

**Run Test**:

```bash
k6 run gmail-search-test.js
```

**Note**: Keep concurrent users low (3-5) to avoid hitting Google API rate limits

---

### Test 4: Mixed Workload

**Objective**: Simulate realistic mixed workload

**k6 Test Script** (`mixed-workload-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const TEST_EMAIL = 'test@gmail.com';

export let options = {
  stages: [
    { duration: '1m', target: 5 },
    { duration: '3m', target: 5 },
    { duration: '30s', target: 0 },
  ],
};

export default function() {
  const baseUrl = 'http://google-workspace.busyb.local:8000';

  // Mix of operations (random selection)
  const operations = [
    // Health check (30%)
    () => {
      const res = http.get(`${baseUrl}/health`);
      check(res, { 'health status 200': (r) => r.status === 200 });
    },
    // Tools list (30%)
    () => {
      const res = http.post(`${baseUrl}/mcp`,
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'tools/list',
          params: {}
        }),
        { headers: { 'Content-Type': 'application/json' } }
      );
      check(res, { 'tools list status 200': (r) => r.status === 200 });
    },
    // Gmail search (20%)
    () => {
      const res = http.post(`${baseUrl}/mcp`,
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'tools/call',
          params: {
            name: 'search_gmail_messages',
            arguments: {
              user_google_email: TEST_EMAIL,
              query: 'is:unread'
            }
          }
        }),
        { headers: { 'Content-Type': 'application/json' } }
      );
      check(res, { 'gmail search status 200': (r) => r.status === 200 });
    },
    // Drive list (20%)
    () => {
      const res = http.post(`${baseUrl}/mcp`,
        JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'tools/call',
          params: {
            name: 'list_drive_files',
            arguments: {
              user_google_email: TEST_EMAIL,
              max_results: 10
            }
          }
        }),
        { headers: { 'Content-Type': 'application/json' } }
      );
      check(res, { 'drive list status 200': (r) => r.status === 200 });
    },
  ];

  // Weighted random selection
  const rand = Math.random();
  if (rand < 0.3) {
    operations[0](); // Health check
  } else if (rand < 0.6) {
    operations[1](); // Tools list
  } else if (rand < 0.8) {
    operations[2](); // Gmail search
  } else {
    operations[3](); // Drive list
  }

  sleep(Math.random() * 3 + 2); // Random sleep 2-5 seconds
}
```

**Run Test**:

```bash
k6 run mixed-workload-test.js
```

---

### Test 5: Stress Test (Find Breaking Point)

**Objective**: Determine maximum capacity before service degrades

**k6 Test Script** (`stress-test.js`):

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp to 10 users
    { duration: '2m', target: 20 },   // Ramp to 20 users
    { duration: '2m', target: 30 },   // Ramp to 30 users
    { duration: '2m', target: 40 },   // Ramp to 40 users
    { duration: '2m', target: 50 },   // Ramp to 50 users
    { duration: '5m', target: 0 },    // Ramp down
  ],
};

export default function() {
  const response = http.get('http://google-workspace.busyb.local:8000/health');

  check(response, {
    'status is 200': (r) => r.status === 200,
  });

  sleep(0.5);
}
```

**Run Test**:

```bash
k6 run stress-test.js
```

**Monitor During Test**:
```bash
# In separate terminal, watch ECS metrics
watch -n 5 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].[runningCount,desiredCount]" \
  --region us-east-1'
```

---

## Monitoring During Tests

### CloudWatch Metrics to Monitor

1. **ECS Service Metrics**:
   - CPUUtilization
   - MemoryUtilization
   - RunningTaskCount
   - DesiredTaskCount

2. **ALB Metrics** (if applicable):
   - TargetResponseTime
   - RequestCount
   - HealthyHostCount
   - UnHealthyHostCount

3. **Application Metrics** (from logs):
   - Request count
   - Error count
   - Response times

### Monitoring Commands

**Watch ECS Metrics**:
```bash
# CPU and Memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -v-10M +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average \
  --region us-east-1
```

**Watch Task Count**:
```bash
watch -n 5 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].[runningCount,desiredCount,pendingCount]" \
  --output table \
  --region us-east-1'
```

**Monitor Logs for Errors**:
```bash
aws logs tail /ecs/busyb-google-workspace-mcp \
  --follow \
  --filter-pattern "ERROR" \
  --region us-east-1
```

---

## Performance Metrics Collection

### Key Performance Indicators (KPIs)

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Health Check P95 | < 100ms | < 200ms | > 500ms |
| Health Check P99 | < 200ms | < 500ms | > 1000ms |
| MCP Tools List P95 | < 500ms | < 1000ms | > 2000ms |
| Gmail Search P95 | < 2s | < 3s | > 5s |
| Error Rate | 0% | < 1% | > 5% |
| CPU Utilization | < 50% | < 70% | > 85% |
| Memory Utilization | < 60% | < 75% | > 90% |

### Data Collection Template

```markdown
# Performance Test Results

**Date**: YYYY-MM-DD
**Tool**: k6 v0.XX.X
**Duration**: Xm Ys
**Configuration**: 0.5 vCPU, 1GB RAM, 1 task

## Test 1: Health Check Baseline

**Load Profile**: 5 → 10 → 20 concurrent users over 5 minutes

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Total Requests | 1,234 | - | - |
| Requests/sec | 4.1 | > 10 | ✅ |
| P50 Response Time | 45ms | < 100ms | ✅ |
| P95 Response Time | 87ms | < 200ms | ✅ |
| P99 Response Time | 123ms | < 500ms | ✅ |
| Error Rate | 0% | < 1% | ✅ |
| Avg CPU | 23% | < 50% | ✅ |
| Avg Memory | 387MB | < 600MB | ✅ |
| Peak CPU | 41% | < 70% | ✅ |
| Peak Memory | 445MB | < 750MB | ✅ |

**Observations**:
- Service handled load comfortably
- No errors observed
- Resource utilization well within limits
- Response times consistent across load levels

## Test 2: MCP Tools List

[Similar format...]

## Test 3: Gmail Search

[Similar format...]

## Test 4: Mixed Workload

[Similar format...]

## Test 5: Stress Test

**Load Profile**: Ramping from 10 to 50 users over 10 minutes

**Breaking Point**:
- Service started showing degradation at: 35 concurrent users
- Error rate increased above 5% at: 42 concurrent users
- CPU reached 85% at: 38 concurrent users
- Memory reached 85% at: 45 concurrent users

**Symptoms at Breaking Point**:
- Response times increased from ~100ms to ~2000ms
- Intermittent 503 errors
- ECS attempted to start additional tasks (if auto-scaling configured)

## Capacity Recommendations

Based on test results:

1. **Current Capacity**: Supports up to 30 concurrent users comfortably
2. **Recommended Threshold for Auto-scaling**: CPU > 60% or Memory > 70%
3. **Recommended Task Count**: 2 tasks for production redundancy
4. **Recommended Resource Increase**: Consider 1 vCPU / 2GB RAM for higher load

## Performance Bottlenecks Identified

1. [Any bottlenecks found]
2. [Optimization opportunities]

## Action Items

- [ ] Implement auto-scaling based on CPU/memory thresholds
- [ ] Increase task count to 2 for redundancy
- [ ] Monitor performance in production
- [ ] Re-test after optimizations
```

---

## Alternative Testing Tools

### Apache Bench (Simple HTTP Load Test)

```bash
# Basic health check load test
ab -n 1000 -c 10 -t 60 http://google-workspace.busyb.local:8000/health

# Explanation:
# -n 1000: Total 1000 requests
# -c 10: 10 concurrent requests
# -t 60: Run for 60 seconds

# MCP tools/list test (POST request)
ab -n 500 -c 5 -p tools-list.json -T 'application/json' \
  http://google-workspace.busyb.local:8000/mcp

# Create tools-list.json:
cat > tools-list.json << 'EOF'
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
EOF
```

### hey (Simple Load Testing)

```bash
# Install hey
go install github.com/rakyll/hey@latest

# Basic load test
hey -n 1000 -c 10 -t 30 http://google-workspace.busyb.local:8000/health

# With custom headers
hey -n 500 -c 5 -m POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  http://google-workspace.busyb.local:8000/mcp
```

---

## Resource Utilization Analysis

### Analyze CloudWatch Logs

```bash
# Count requests per minute
aws logs filter-log-events \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --start-time $(date -u -v-1H +%s)000 \
  --filter-pattern "[timestamp, request_id, level=INFO, msg=\"*Request*\"]" \
  --region us-east-1 | \
  jq -r '.events[].message' | wc -l

# Find slowest requests
aws logs filter-log-events \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --start-time $(date -u -v-1H +%s)000 \
  --filter-pattern "[timestamp, request_id, level, msg=\"*duration*\"]" \
  --region us-east-1 | \
  jq -r '.events[].message' | \
  grep -o 'duration=[0-9.]*' | \
  sort -t= -k2 -n -r | head -10
```

### Calculate Resource Requirements

```python
# calculate-resources.py
# Estimate required resources based on test results

import json

# Test results
concurrent_users = 30  # Max comfortable load
requests_per_user_per_minute = 10  # From test
avg_response_time_ms = 150  # From test
peak_cpu_percent = 41  # From test
peak_memory_mb = 445  # From test

# Calculate total RPS
total_rps = (concurrent_users * requests_per_user_per_minute) / 60
print(f"Total requests/second: {total_rps:.1f}")

# Calculate concurrent requests
avg_concurrent = (total_rps * avg_response_time_ms) / 1000
print(f"Average concurrent requests: {avg_concurrent:.1f}")

# Estimate scaling requirement
target_users = 100  # Target capacity
scaling_factor = target_users / concurrent_users
required_cpu = peak_cpu_percent * scaling_factor
required_memory = peak_memory_mb * scaling_factor

print(f"\nFor {target_users} concurrent users:")
print(f"Required CPU: {required_cpu:.0f}% ({required_cpu/50:.1f} vCPUs)")
print(f"Required Memory: {required_memory:.0f}MB")
print(f"Recommended tasks: {int(scaling_factor) + 1}")
```

---

## Auto-Scaling Configuration (Future Enhancement)

Based on performance test results, configure auto-scaling:

```bash
# Create auto-scaling target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 1 \
  --max-capacity 4 \
  --region us-east-1

# Create CPU-based scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 60.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 60,
    "ScaleInCooldown": 180
  }' \
  --region us-east-1

# Create Memory-based scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name memory-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageMemoryUtilization"
    },
    "ScaleOutCooldown": 60,
    "ScaleInCooldown": 180
  }' \
  --region us-east-1
```

---

## Performance Testing Checklist

- [ ] Install load testing tool (k6/ab/hey)
- [ ] Verify service is healthy before testing
- [ ] Run baseline health check test
- [ ] Run MCP tools list test
- [ ] Run authenticated Gmail/Drive tests
- [ ] Run mixed workload test
- [ ] Run stress test to find breaking point
- [ ] Monitor CloudWatch metrics during all tests
- [ ] Collect and analyze results
- [ ] Document performance characteristics
- [ ] Identify bottlenecks
- [ ] Create recommendations for scaling
- [ ] Update capacity planning documentation

---

## Next Steps

After performance testing:

1. ✅ Document test results and findings
2. ✅ Update capacity recommendations
3. ✅ Add auto-scaling configuration (if needed)
4. ➡️ Proceed to Task 5.10: Create Production Runbook
5. ➡️ Include performance metrics in monitoring plan
