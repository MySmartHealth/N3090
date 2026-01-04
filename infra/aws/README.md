# AWS Control Plane (Provisioning Blueprint)

## Scope
- Identity & Consent (Cognito/User Pool + custom consent store)
- Workflow Engine (Step Functions + EventBridge)
- Rules Engine (Lambda + DynamoDB/JSONLogic)
- Audit Logging (S3 with Object Lock + Athena)
- Node Registry (DynamoDB) + Heartbeats (API Gateway + Lambda)

## Networking
- Private API Gateway with WAF
- Tailscale/VPN peering for local nodes
- No inbound to nodes from Internet; AWS-initiated requests only

## Notes
- All PHI persistence on AWS services
- Local nodes are stateless workers registered via short-lived credentials
- Fallback routing to cloud LLMs when local capacity is unavailable
