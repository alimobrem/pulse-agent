# Sysadmin Customer Review Memory

## Project: OpenShift Pulse v4.2.0 (Frontend)
- 14 views, 35 routes, ~120 production files, 1269+ tests
- React 19 + TypeScript 5.9 + Rspack + Tailwind
- See `argocd-review.md` and `agent-review.md` for frontend details

## Pulse Agent Backend v0.2.0 (FINAL SIGN-OFF 2026-03-24)
- Python 3.11+, FastAPI WS + Rich CLI, Anthropic Claude streaming
- Root: `/Users/amobrem/ali/open/` -- uses `chart/` and `sre_agent/`
- 18 source files, 6 memory module files, 13 test files (199 tests)
- 67 tools: 55 SRE (45 k8s + 4 gitops + 1 timeline + 2 git + 3 predict) + 9 security + 3 memory
- 4 pillars: ArgoCD Shadow, Time Machine, Ghost in the Machine, The Prophet
- Helm chart: 8 templates, tiered RBAC, NetworkPolicy, UBI9 Dockerfile
- Self-improving memory: SQLite incidents/runbooks/patterns/metrics
- VERDICT: GO -- all blockers from previous reviews resolved

## Security Architecture (Verified)
1. WS auth mandatory: api.py L209-215, hmac.compare_digest
2. on_confirm=None denies: agent.py L327, fail-closed
3. apply_yaml blocked kinds: k8s_tools.py L1709-1713
4. System prompt injection defense: agent.py L136-148
5. Context sanitization: api.py L48-56
6. Circuit breaker: agent.py L34-91
7. Rate limiting: api.py L45 (10/min per connection)
8. Git PR: repo allowlist via PULSE_ALLOWED_REPOS, path traversal check, per-session limit

## Previous Blockers -- ALL RESOLVED
1. No WS auth -> mandatory token + hmac
2. No pillar tests -> 199 tests across 13 files
3. No repo allowlist for git PRs -> PULSE_ALLOWED_REPOS env var
4. Hardcoded Alertmanager -> configurable via ALERTMANAGER_URL/SVC/NS env vars
5. forecast_quota_exhaustion snapshot-only -> now has Prometheus deriv() trending

## Minor Non-Blocking Issues (Still Open)
- _extract_namespace regex [\w.-] allows underscores (K8s DNS forbids)
- get_pod_logs L184 startswith("Error") false-positive risk
- get_tls_certificates L1510 ssl._ssl._test_decode_cert(None) is dead code
- No CLI REPL integration test
- NetworkPolicy egress allows all destinations on 443/6443

## Feature Backlog v0.3.0
1. Multi-cluster agent support (HIGH)
2. Slack/PagerDuty integration (HIGH)
3. Per-IP WS rate limiting (MEDIUM)
4. Proper TLS cert parsing via cryptography lib (MEDIUM)
5. ArgoCD server API for full diffs (MEDIUM)
6. Multi-source ArgoCD support (MEDIUM)
7. Cost visibility tools -- OpenCost integration (NICE)

## Competitor Patterns
- k8sgpt: CLI-first AI diagnostics, webhook integration
- Botkube: Slack-native K8s ops
- Robusta: AI troubleshooting with runbooks, Slack alerts
- Kubecost/OpenCost: cost per namespace/workload
