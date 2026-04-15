# Retail Payment Gateway Degradation Runbook

## Scope
Use this runbook when card authorization latency rises above 2 seconds or success rate drops below 97% for 5 minutes.

## Immediate Actions (0-10 min)
1. Declare SEV2 incident and assign incident commander.
2. Confirm blast radius by store region and payment type (chip, swipe, contactless).
3. Switch checkout terminals to offline authorization mode for impacted stores.
4. Notify store managers in impacted regions with expected customer messaging.

## Technical Triage
1. Check payment gateway status dashboard and API error rates.
2. Compare gateway p95 latency against baseline.
3. Validate DNS and outbound firewall paths from store network edge.
4. Confirm retry policy is enabled (max 2 retries with jittered backoff).

## Escalation
- Escalate to vendor support if p95 latency > 3 seconds for 10 minutes.
- Escalate to network on-call if packet loss > 2% on gateway path.
- Escalate to finance systems on-call if settlement queue grows continuously for 15 minutes.

## Customer/Store Communications
- Post updates every 15 minutes in #incident-bridge.
- Use approved message: "Card processing may be delayed. Please keep customer at checkout until confirmation."

## Exit Criteria
- Authorization success rate >= 99% for 15 consecutive minutes.
- p95 latency <= 1.5 seconds for 15 consecutive minutes.
- Settlement queue backlog is draining.

## Post-Incident
- Record first-detection time, mitigation time, full recovery time.
- Attach gateway graphs and store impact summary to incident ticket.
- Add follow-up tasks for retry tuning and vendor escalation automation.
