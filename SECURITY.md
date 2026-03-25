# Security Policy

## Reporting Vulnerabilities

Report security issues to [GitHub Issues](https://github.com/alimobrem/pulse-agent/issues) with the `security` label.

## Security Model

### Authentication
- WebSocket API requires `PULSE_AGENT_WS_TOKEN` (constant-time comparison via `hmac.compare_digest`)
- In production, deploy behind OpenShift OAuth proxy — the agent service should not be exposed directly
- Rate limited to 10 messages/minute per WebSocket connection

### Authorization
- Agent uses the pod's ServiceAccount for K8s API calls (not user impersonation)
- RBAC is least-privilege: read-only by default, write operations opt-in via `rbac.allowWriteOperations`
- Secret access opt-in via `rbac.allowSecretAccess`
- No wildcard RBAC rules

### Input Sanitization
- Context fields (kind, namespace, name) validated against `^[a-zA-Z0-9\-._/: ]{0,253}$`
- Non-matching values rejected entirely (strict mode)
- WebSocket messages capped at 1MB
- Tool inputs bounds-checked (replicas 0-100, log lines 1-1000, grace period 1-300s)

### Prompt Injection Defense
- System prompt includes explicit security rules against tool-result injection
- Confirmation gates enforced in code (not just prompt instructions)
- Write tools require programmatic user approval before execution

### Container Security
- Non-root user (UID 1001) on RHEL UBI9 base
- `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]`
- `seccompProfile: RuntimeDefault`
- Liveness/readiness probes via `/healthz`

### Audit Trail
- All tool executions logged to structured JSON (`pulse_agent_audit.log`)
- Cluster-side audit via `record_audit_entry` tool (writes to ConfigMap)
- Retry-on-409 for concurrent audit writes

### Network
- Egress restricted to DNS (port 53) and HTTPS (443/6443)
- Ingress limited to port 8080 (WebSocket/HTTP)
