"""
Marmot Quick Start Example

Run: python -m examples.quickstart
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import marmot

# ─── Step 1: Configure ────────────────────────────────────────────
marmot.configure(":memory:", start_escalation=False)

# ─── Step 2: Register Notifiers ──────────────────────────────────
marmot.register_notifier("console", marmot.ConsoleNotifier())

# ─── Step 3: Register Threshold Rule ──────────────────────────────
# CPU monitoring with multi-level thresholds
marmot.register_threshold_rule(marmot.ThresholdRule(
    name="cpu_usage",
    thresholds=[
        marmot.ThresholdLevel(value=70, severity="info"),
        marmot.ThresholdLevel(value=80, severity="warning"),
        marmot.ThresholdLevel(value=90, severity="error"),
        marmot.ThresholdLevel(value=95, severity="critical"),
    ],
    consecutive_count=2,       # Need 2 consecutive hits to fire
    silence_seconds=60,        # Silence for 60s after firing
    notify_targets=["console"],
))

# ─── Step 4: Report metrics ───────────────────────────────────────
print("=== Simulating CPU monitoring ===\n")

# First report — pending (need 2 consecutive)
e = marmot.report("cpu_usage", 85.0, labels={"host": "prod-1"})
print(f"Report 85.0 → state={e.state}")

# Second report — fires!
e = marmot.report("cpu_usage", 87.0, labels={"host": "prod-1"})
print(f"Report 87.0 → state={e.state}  severity={e.severity}")

# Upgrade to critical
e = marmot.report("cpu_usage", 96.0, labels={"host": "prod-1"})
print(f"Report 96.0 → state={e.state}  severity={e.severity}")

# Recover
e = marmot.report("cpu_usage", 45.0, labels={"host": "prod-1"})
print(f"Report 45.0 → state={e.state}")

print()

# ─── Step 5: Manual fire ─────────────────────────────────────────
print("=== Manual alert ===\n")
event = marmot.fire(
    "payment_failure",
    "Payment gateway timeout — 5 consecutive failures",
    severity="critical",
    labels={"service": "payments"},
    notify_targets=["console"],
)
print(f"Fired: state={event.state}  id={event.id}")

print()

# ─── Step 6: Job decorator ────────────────────────────────────────
print("=== Job monitoring ===\n")

@marmot.job("cleanup", timeout="30m", notify="console")
def cleanup_job():
    print("  Running cleanup...")
    return "done"

cleanup_job()

print()

# ─── Step 7: Heartbeat ───────────────────────────────────────────
print("=== Heartbeat ===\n")
marmot.register_rule(marmot.Rule.from_inputs(
    name="data_pipeline", expected_interval="5m", notify="console",
))

# Miss → fire
marmot.fire("data_pipeline", "Heartbeat missed for 15m",
            notify_targets=["console"])

# Ping → resolve
marmot.ping("data_pipeline", message="Pipeline back online")

print()

# ─── Step 8: Manual resolve ──────────────────────────────────────
print("=== Manual resolve ===\n")
marmot.fire("disk_space", "Disk usage at 98%",
            severity="critical", notify_targets=["console"])
marmot.resolve("disk_space", message="Disk cleaned up")

print("\n=== Done! ===")

# Cleanup
marmot.shutdown()
