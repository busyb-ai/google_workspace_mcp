# Monitoring and Alerting Plan

## Overview

This document outlines the comprehensive monitoring and alerting strategy for the Google Workspace MCP service, including current capabilities and future enhancements.

## Table of Contents

1. [Current Monitoring](#current-monitoring)
2. [Future Monitoring Enhancements](#future-monitoring-enhancements)
3. [Alerting Strategy](#alerting-strategy)
4. [Dashboards](#dashboards)
5. [Log Analysis](#log-analysis)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Current Monitoring

### What We Have Today

#### 1. CloudWatch Logs

**Location**: `/ecs/busyb-google-workspace-mcp`

**What's Logged**:
- Application startup/shutdown
- Request processing
- OAuth authentication flows
- Tool invocations
- Errors and exceptions
- Performance metrics (response times)

**Access**:
```bash
# View recent logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --region us-east-1

# Live streaming
aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1

# Filter errors
aws logs tail /ecs/busyb-google-workspace-mcp --filter-pattern "ERROR" --region us-east-1
```

#### 2. ECS Service Metrics

**Available Metrics**:
- Running task count
- Desired task count
- Pending task count
- CPU utilization
- Memory utilization
- Service events (deployments, scaling, errors)

**Access**:
```bash
# Service status
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1

# Task status
aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --region us-east-1
```

#### 3. Health Check Endpoint

**Endpoint**: `GET http://google-workspace.busyb.local:8000/health`

**Response**:
```json
{
  "status": "healthy",
  "service": "workspace-mcp",
  "version": "1.0.0",
  "transport": "streamable-http"
}
```

**Usage**:
- Manual health verification
- External monitoring systems
- Load balancer health checks

#### 4. Basic CloudWatch Dashboards

**Default AWS Dashboards**:
- ECS cluster metrics
- Fargate task metrics
- CloudWatch Logs Insights

#### 5. GitHub Actions Deployment Logs

**What's Monitored**:
- Deployment success/failure
- Build duration
- Test results (if configured)
- Deployment timeline

**Access**: GitHub Actions tab in repository

---

## Future Monitoring Enhancements

### Phase 1: Essential Monitoring (High Priority)

#### 1.1 CloudWatch Alarms

**Service Health Alarms**:

**High CPU Utilization**:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name google-workspace-mcp-high-cpu \
  --alarm-description "Alert when CPU > 80% for 5 minutes" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:ops-alerts \
  --region us-east-1
```

**High Memory Utilization**:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name google-workspace-mcp-high-memory \
  --alarm-description "Alert when Memory > 80% for 5 minutes" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1 \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:ops-alerts \
  --region us-east-1
```

**Task Failures**:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name google-workspace-mcp-task-stopped \
  --alarm-description "Alert when tasks stop unexpectedly" \
  --metric-name RunningTaskCount \
  --namespace ECS/ContainerInsights \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:critical-alerts \
  --region us-east-1
```

**Health Check Failures**:
```bash
# Use ALB target health metric if ALB configured
aws cloudwatch put-metric-alarm \
  --alarm-name google-workspace-mcp-health-check-failed \
  --alarm-description "Alert when health checks fail" \
  --metric-name UnHealthyHostCount \
  --namespace AWS/ApplicationELB \
  --statistic Average \
  --period 60 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 2 \
  --dimensions Name=TargetGroup,Value=<target-group-arn> Name=LoadBalancer,Value=<load-balancer-arn> \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:critical-alerts \
  --region us-east-1
```

**Error Rate Alarm**:
```bash
# Create metric filter first
aws logs put-metric-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name ErrorCount \
  --filter-pattern "ERROR" \
  --metric-transformations \
    metricName=ErrorCount,metricNamespace=GoogleWorkspaceMCP,metricValue=1,defaultValue=0 \
  --region us-east-1

# Then create alarm
aws cloudwatch put-metric-alarm \
  --alarm-name google-workspace-mcp-high-error-rate \
  --alarm-description "Alert when error rate > 10 errors/minute" \
  --metric-name ErrorCount \
  --namespace GoogleWorkspaceMCP \
  --statistic Sum \
  --period 60 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --treat-missing-data notBreaching \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:ops-alerts \
  --region us-east-1
```

**SNS Topic Setup**:
```bash
# Create SNS topics for alerts
aws sns create-topic --name ops-alerts --region us-east-1
aws sns create-topic --name critical-alerts --region us-east-1

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:590183811329:ops-alerts \
  --protocol email \
  --notification-endpoint ops@busyb.ai \
  --region us-east-1

aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:590183811329:critical-alerts \
  --protocol email \
  --notification-endpoint oncall@busyb.ai \
  --region us-east-1
```

#### 1.2 Custom Application Metrics

**Metrics to Implement**:

| Metric | Type | Description | Threshold |
|--------|------|-------------|-----------|
| oauth_success_rate | Percentage | OAuth authentication success rate | < 95% |
| oauth_attempts | Counter | Total OAuth attempts | Monitor trend |
| tool_invocation_count | Counter | Tool calls by tool name | Monitor trend |
| tool_error_rate | Percentage | Tool errors by tool name | > 5% |
| api_response_time_p95 | Duration | 95th percentile response time | > 3s |
| api_response_time_p99 | Duration | 99th percentile response time | > 5s |
| s3_operation_duration | Duration | S3 read/write latency | > 1s |
| google_api_rate_limit | Counter | Rate limit hits | > 0 |
| active_users | Gauge | Active authenticated users | Monitor trend |
| credential_refresh_count | Counter | Token refreshes | Monitor trend |

**Implementation Example** (using CloudWatch Embedded Metric Format):

```python
# In application code
from aws_embedded_metrics import metric_scope

@metric_scope
def track_oauth_attempt(metrics, success: bool):
    metrics.put_metric("OAuthAttempt", 1, "Count")
    if success:
        metrics.put_metric("OAuthSuccess", 1, "Count")
    else:
        metrics.put_metric("OAuthFailure", 1, "Count")
    metrics.set_namespace("GoogleWorkspaceMCP")
    metrics.set_property("Timestamp", datetime.utcnow().isoformat())

@metric_scope
def track_tool_invocation(metrics, tool_name: str, duration_ms: float, success: bool):
    metrics.put_metric("ToolInvocation", 1, "Count")
    metrics.put_metric("ToolDuration", duration_ms, "Milliseconds")
    metrics.set_dimensions({"ToolName": tool_name})
    metrics.set_namespace("GoogleWorkspaceMCP")

    if not success:
        metrics.put_metric("ToolError", 1, "Count")
```

#### 1.3 Log-Based Metrics

**CloudWatch Metric Filters**:

**OAuth Success Rate**:
```bash
# OAuth successes
aws logs put-metric-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name OAuthSuccess \
  --filter-pattern "[timestamp, level, msg=\"*OAuth*success*\"]" \
  --metric-transformations \
    metricName=OAuthSuccess,metricNamespace=GoogleWorkspaceMCP,metricValue=1 \
  --region us-east-1

# OAuth failures
aws logs put-metric-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name OAuthFailure \
  --filter-pattern "[timestamp, level, msg=\"*OAuth*failed*\"]" \
  --metric-transformations \
    metricName=OAuthFailure,metricNamespace=GoogleWorkspaceMCP,metricValue=1 \
  --region us-east-1
```

**Slow Requests**:
```bash
aws logs put-metric-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name SlowRequests \
  --filter-pattern "[timestamp, level, msg, duration > 3000]" \
  --metric-transformations \
    metricName=SlowRequests,metricNamespace=GoogleWorkspaceMCP,metricValue=1 \
  --region us-east-1
```

**S3 Errors**:
```bash
aws logs put-metric-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name S3Error \
  --filter-pattern "[timestamp, level=ERROR, msg=\"*S3*\"]" \
  --metric-transformations \
    metricName=S3Error,metricNamespace=GoogleWorkspaceMCP,metricValue=1 \
  --region us-east-1
```

---

### Phase 2: Advanced Monitoring (Medium Priority)

#### 2.1 Distributed Tracing with AWS X-Ray

**Benefits**:
- End-to-end request tracing
- Identify bottlenecks
- Visualize service dependencies
- Performance analysis

**Implementation**:
1. Install X-Ray SDK
2. Instrument application code
3. Enable X-Ray on ECS task
4. Configure X-Ray daemon sidecar

**Example Task Definition Addition**:
```json
{
  "name": "xray-daemon",
  "image": "public.ecr.aws/xray/aws-xray-daemon:latest",
  "cpu": 32,
  "memoryReservation": 256,
  "portMappings": [
    {
      "containerPort": 2000,
      "protocol": "udp"
    }
  ]
}
```

#### 2.2 Custom CloudWatch Dashboard

**Dashboard Components**:
1. Service health overview
2. Resource utilization (CPU, memory)
3. Request metrics (rate, latency, errors)
4. OAuth metrics
5. Tool usage metrics
6. Error rate timeline
7. Active users
8. Deployment timeline

**Create Dashboard**:
```bash
aws cloudwatch put-dashboard \
  --dashboard-name GoogleWorkspaceMCP \
  --dashboard-body file://dashboard.json \
  --region us-east-1
```

**Dashboard JSON Example** (`dashboard.json`):
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
          [".", "MemoryUtilization", {"stat": "Average"}]
        ],
        "period": 300,
        "stat": "Average",
        "region": "us-east-1",
        "title": "Resource Utilization",
        "yAxis": {
          "left": {"min": 0, "max": 100}
        }
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["GoogleWorkspaceMCP", "OAuthSuccess", {"stat": "Sum"}],
          [".", "OAuthFailure", {"stat": "Sum", "color": "#d13212"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "OAuth Metrics"
      }
    },
    {
      "type": "log",
      "properties": {
        "query": "SOURCE '/ecs/busyb-google-workspace-mcp' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20",
        "region": "us-east-1",
        "title": "Recent Errors"
      }
    }
  ]
}
```

#### 2.3 Log Aggregation and Analysis

**Enhanced CloudWatch Insights Queries**:

**Request Rate by Tool**:
```sql
fields @timestamp, tool_name
| filter @message like /tool invocation/
| parse @message "tool=* " as tool_name
| stats count() by tool_name
| sort count() desc
```

**Error Rate Over Time**:
```sql
fields @timestamp
| filter @message like /ERROR/
| stats count() as error_count by bin(5m)
```

**P95/P99 Response Times**:
```sql
fields @timestamp, duration
| filter @message like /duration/
| parse @message "duration=*ms" as duration
| stats percentile(duration, 50) as p50,
        percentile(duration, 95) as p95,
        percentile(duration, 99) as p99
        by bin(5m)
```

**OAuth Success Rate**:
```sql
fields @timestamp
| filter @message like /OAuth/
| parse @message "*OAuth*" as oauth_event
| stats count(@message like /success/) as successes,
        count(@message like /failed/) as failures
| extend total = successes + failures
| extend success_rate = successes * 100.0 / total
```

**User Activity**:
```sql
fields @timestamp, user_email
| filter @message like /user_google_email/
| parse @message "user_google_email=* " as user_email
| stats count() by user_email
| sort count() desc
| limit 20
```

**S3 Performance**:
```sql
fields @timestamp, duration
| filter @message like /S3/
| parse @message "duration=*ms" as duration
| stats avg(duration) as avg_s3_latency,
        percentile(duration, 95) as p95_s3_latency
        by bin(5m)
```

---

### Phase 3: Enhanced Observability (Lower Priority)

#### 3.1 Structured Logging

**Current**: Plain text logs
**Future**: JSON structured logs

**Benefits**:
- Easier parsing
- Better filtering
- Richer context
- Better integration with log analysis tools

**Example Structured Log**:
```json
{
  "timestamp": "2025-01-12T10:30:00.000Z",
  "level": "INFO",
  "message": "Tool invoked",
  "context": {
    "tool_name": "search_gmail_messages",
    "user_email": "user@example.com",
    "duration_ms": 145,
    "success": true,
    "request_id": "abc123"
  }
}
```

#### 3.2 Real-Time Anomaly Detection

**Use CloudWatch Anomaly Detection**:
- Automatically detect unusual patterns
- Adaptive thresholds
- Reduce false positives

**Example**:
```bash
aws cloudwatch put-anomaly-detector \
  --namespace GoogleWorkspaceMCP \
  --metric-name ErrorCount \
  --stat Sum \
  --region us-east-1
```

#### 3.3 Cost Monitoring

**Track Costs**:
- ECS Fargate costs
- S3 storage and requests
- CloudWatch logs storage
- Data transfer
- ECR storage

**AWS Cost Explorer**:
- Tag resources for cost allocation
- Create cost anomaly alerts
- Budget alerts

---

## Alerting Strategy

### Alert Severity Levels

| Severity | Response Time | Notification Method | Example |
|----------|---------------|---------------------|---------|
| **Critical** | Immediate (< 15 min) | PagerDuty, SMS, Email, Slack | Service down, all tasks failed |
| **High** | < 1 hour | Email, Slack | High error rate, resource exhaustion |
| **Medium** | < 4 hours | Email, Slack | Elevated errors, slow performance |
| **Low** | < 24 hours | Email | Minor issues, informational |

### Alert Routing

#### Critical Alerts (SNS Topic: `critical-alerts`)

**Conditions**:
- All tasks stopped
- Health checks failing for > 2 minutes
- Error rate > 50%
- Service completely unavailable

**Recipients**:
- On-call engineer (PagerDuty)
- Engineering manager (SMS)
- Operations team (Slack #alerts-critical)

#### High Priority Alerts (SNS Topic: `ops-alerts`)

**Conditions**:
- CPU > 80% for 5 minutes
- Memory > 80% for 5 minutes
- Error rate > 10%
- Individual tasks failing repeatedly
- OAuth success rate < 90%

**Recipients**:
- Operations team (Slack #alerts-ops)
- Engineering team (Email)

#### Medium Priority Alerts (SNS Topic: `warnings`)

**Conditions**:
- CPU > 60% for 10 minutes
- Memory > 70% for 10 minutes
- Error rate > 5%
- Slow response times (P95 > 3s)
- Google API rate limits hit

**Recipients**:
- Engineering team (Email)
- Ops team (Slack #alerts-warnings)

#### Low Priority Alerts (SNS Topic: `info`)

**Conditions**:
- Deployments completed
- Configuration changes
- Scaling events
- Token refreshes increasing

**Recipients**:
- Engineering team (Email, aggregated daily)

### Alert Fatigue Mitigation

**Strategies**:
1. **Appropriate Thresholds**: Tune thresholds to reduce noise
2. **Evaluation Periods**: Require sustained conditions, not transient spikes
3. **Composite Alarms**: Combine multiple conditions
4. **Alert Suppression**: Suppress known issues during maintenance
5. **Escalation Policies**: Escalate only if unacknowledged
6. **Alert Grouping**: Group related alerts

**Example Composite Alarm**:
```bash
# Only alert if BOTH CPU high AND error rate elevated
aws cloudwatch put-composite-alarm \
  --alarm-name google-workspace-mcp-degraded-performance \
  --alarm-description "Service experiencing degraded performance" \
  --alarm-rule "ALARM(google-workspace-mcp-high-cpu) AND ALARM(google-workspace-mcp-high-error-rate)" \
  --actions-enabled \
  --alarm-actions arn:aws:sns:us-east-1:590183811329:ops-alerts \
  --region us-east-1
```

---

## Dashboards

### Dashboard 1: Service Health Overview

**Widgets**:
- Service status (running/desired/pending tasks)
- Health check status
- Error rate (last 24h)
- CPU utilization
- Memory utilization
- Request rate
- Recent deployment timeline

**URL**: CloudWatch Dashboard link

---

### Dashboard 2: Performance Dashboard

**Widgets**:
- Request rate over time
- P50/P95/P99 response times
- Error rate percentage
- Slow requests (> 3s)
- Tool invocation breakdown
- OAuth flow durations
- S3 operation latencies

---

### Dashboard 3: OAuth Dashboard

**Widgets**:
- OAuth attempts (success/failure)
- OAuth success rate
- Token refreshes
- Active users
- Credentials stored in S3
- OAuth errors by type

---

### Dashboard 4: Cost Dashboard

**Widgets**:
- Daily cost trend
- Cost by service (ECS, S3, CloudWatch, etc.)
- Cost anomalies
- Budget vs actual
- Forecast

---

## Log Analysis

### Automated Log Analysis

#### Daily Log Summary (Lambda)

**Purpose**: Generate daily summary of service health

**Metrics to Include**:
- Total requests
- Error rate
- Top errors
- Tool usage
- OAuth success rate
- Average response time
- Active users

**Implementation**:
```python
# lambda_function.py
import boto3
from datetime import datetime, timedelta

logs = boto3.client('logs')

def lambda_handler(event, context):
    log_group = '/ecs/busyb-google-workspace-mcp'
    start_time = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
    end_time = int(datetime.now().timestamp() * 1000)

    # Query for error count
    query = """
    fields @timestamp, @message
    | filter @message like /ERROR/
    | stats count() as error_count
    """

    query_id = logs.start_query(
        logGroupName=log_group,
        startTime=start_time,
        endTime=end_time,
        queryString=query
    )

    # Wait for results and send summary email
    # ... (implementation details)
```

#### Real-Time Error Alerts

**CloudWatch Logs Subscription Filter**:
```bash
aws logs put-subscription-filter \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --filter-name CriticalErrorAlerts \
  --filter-pattern "ERROR" \
  --destination-arn arn:aws:lambda:us-east-1:590183811329:function:error-alert-handler \
  --region us-east-1
```

---

## Implementation Roadmap

### Immediate (Week 1)

- [ ] Create SNS topics for alerts
- [ ] Configure CloudWatch alarms (CPU, memory, task count)
- [ ] Create basic CloudWatch dashboard
- [ ] Subscribe email addresses to alert topics
- [ ] Document alert response procedures

### Short-Term (Weeks 2-4)

- [ ] Implement log-based metric filters
- [ ] Create error rate alarms
- [ ] Enhance logging with request IDs
- [ ] Create performance dashboard
- [ ] Set up CloudWatch Insights queries
- [ ] Implement daily log summary

### Medium-Term (Months 2-3)

- [ ] Implement custom application metrics
- [ ] Create OAuth-specific dashboard
- [ ] Set up X-Ray distributed tracing
- [ ] Implement anomaly detection
- [ ] Create cost monitoring dashboard
- [ ] Optimize alert thresholds based on data

### Long-Term (Months 4-6)

- [ ] Migrate to structured logging
- [ ] Implement predictive alerting
- [ ] Create SLA monitoring
- [ ] Implement automated remediation
- [ ] Set up log retention policies
- [ ] Integrate with incident management system

---

## Cost Estimation

### Monthly Monitoring Costs (Estimated)

| Service | Usage | Cost |
|---------|-------|------|
| CloudWatch Logs | 10 GB ingestion, 10 GB storage | ~$6 |
| CloudWatch Metrics | 50 custom metrics | ~$15 |
| CloudWatch Alarms | 10 alarms | ~$1 |
| CloudWatch Dashboards | 3 dashboards | ~$9 |
| X-Ray (optional) | 1M traces/month | ~$5 |
| SNS | 1000 notifications/month | ~$0.50 |
| **Total** | | **~$36.50/month** |

**Note**: Costs may vary based on actual usage

---

## Success Metrics

Track these metrics to measure monitoring effectiveness:

| Metric | Target | Current |
|--------|--------|---------|
| **MTTR** (Mean Time To Resolution) | < 30 min | TBD |
| **MTTD** (Mean Time To Detection) | < 5 min | TBD |
| **Alert Accuracy** (true positives) | > 90% | TBD |
| **Incident Response Time** | < 15 min | TBD |
| **Service Availability** | > 99.9% | TBD |
| **False Positive Rate** | < 10% | TBD |

---

## Related Documentation

- **Production Runbook**: [docs/runbook.md](./runbook.md)
- **Architecture**: [docs/architecture.md](./architecture.md)
- **Troubleshooting**: [docs/runbook.md#troubleshooting-guide](./runbook.md#troubleshooting-guide)
- **Performance Testing**: [agent_notes/task_5.9_performance_testing.md](../agent_notes/task_5.9_performance_testing.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-12
**Next Review**: 2025-02-12
**Owner**: DevOps Team
