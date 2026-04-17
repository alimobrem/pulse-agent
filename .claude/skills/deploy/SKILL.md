---
name: deploy
description: |
  Deploy Pulse to an OpenShift cluster with pre-flight checks and health verification.
  Use when the user says "deploy", "push to cluster", "roll out", "ship to prod",
  "deploy to openshift", or wants to update the running application. Handles cluster
  selection, dry-run, rollback, and post-deploy verification.
---

# Pulse Deploy

Deploy both the UI and Agent to OpenShift with safety checks.

## Pre-flight

1. Verify cluster login:
```bash
oc whoami 2>&1 || echo "NOT LOGGED IN — run: oc login <cluster-url>"
oc whoami --show-server
```

2. Check for uncommitted changes:
```bash
git status --short
cd /Users/amobrem/ali/OpenshiftPulse && git status --short
```

Warn if there are uncommitted changes — images will be tagged `-dirty`.

3. Run quick verification (skip if user says "fast" or "quick"):
```bash
python3 -m pytest tests/ -x -q 2>&1 | tail -3
cd /Users/amobrem/ali/OpenshiftPulse && npm run type-check 2>&1 | tail -1
```

## Deploy

### Standard Deploy
```bash
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh
```

### Dry Run
If user asks for dry run or preview:
```bash
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --dry-run
```

### With MCP Enabled
```bash
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --set agent.mcp.enabled=true
```

## Post-Deploy Verification

After deploy completes:

1. Verify agent version:
```bash
oc exec -n openshiftpulse deploy/pulse-openshift-sre-agent -- cat /opt/app-root/src/pyproject.toml | grep version | head -1
```

2. Check pod health:
```bash
oc get pods -n openshiftpulse --no-headers
```

3. Report the URL and version to the user.

## Rollback

If user asks to rollback:
```bash
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --rollback
```

## Quick Reference
```
/deploy              # standard deploy
/deploy --dry-run    # preview without applying
/deploy --rollback   # roll back to previous revision
```
