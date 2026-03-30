# Retail Network Escalation Runbook

If more than 3 stores in one region report payment terminal failures within 15 minutes:

1. Open incident channel and assign incident commander.
2. Validate WAN provider health dashboard and DNS health.
3. Switch affected stores to offline payment mode where supported.
4. Notify support desks with approved customer messaging.
5. Capture timeline checkpoints every 15 minutes until recovery.

Post-incident:
- Record affected stores, outage duration, and payment fallout.
- Create follow-up actions for monitoring and failover testing.
