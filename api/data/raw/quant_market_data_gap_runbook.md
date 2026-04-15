# Quant Market Data Gap Runbook

## Trigger
Activate this runbook when market data feed gaps exceed 2 seconds for liquid symbols or 5 seconds for less-liquid symbols.

## Detection Signals
- Feed heartbeat missing for 3 consecutive intervals.
- Tick sequence number jump without replay catch-up.
- Strategy stale-price guardrails firing repeatedly.

## Immediate Risk Controls
1. Put affected strategies into safe mode (reduce order rate to 0 or pause).
2. Disable new strategy launches for impacted venues.
3. Notify trading operations and risk in #incident-bridge.

## Triage Workflow
1. Identify impacted feed handlers and venues.
2. Compare primary and backup feed latency.
3. Verify packet drop and NIC saturation on feed hosts.
4. Check decoder exceptions and sequence-gap counters.
5. Attempt replay recovery from feed provider.

## Escalation
- Escalate to exchange/market-data vendor if replay is unavailable for > 5 minutes.
- Escalate to infrastructure on-call if packet loss > 1% or host CPU > 90% sustained.

## Recovery
1. Confirm sequence continuity restored.
2. Verify strategy warm-up with fresh tick snapshots.
3. Gradually re-enable strategies in controlled batches.

## Exit Criteria
- No sequence gaps for 15 minutes.
- Strategy stale-price alerts return to baseline.
- Risk signs off before full trading resume.
