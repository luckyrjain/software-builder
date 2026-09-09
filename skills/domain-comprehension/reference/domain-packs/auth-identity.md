# Domain pack: auth-identity

Pack for authentication, authorization, identity, and session management domains.

Merge into `domain-config.yaml` at Session 0.

## domain

```yaml
domain:
  name: auth
  display_name: Auth & Identity
  description: Authentication, authorization, session lifecycle, and identity federation
```

## scope

```yaml
scope:
  include_keywords:
    - auth
    - identity
    - token
    - session
    - permission
    - role
    - oauth
    - oidc
    - saml
    - jwt
    - sso
  exclude_patterns:
    - '*-mock*'
    - '*-stub*'
  seed_repos: []          # fill in with your repo names
  conditional_repos: []   # e.g., rate-limiting-service, audit-service
```

## context

```yaml
context:
  regulatory_notes: Replace with applicable compliance scope (GDPR, SOC2, etc.)
  product_lines:
    - name: web
      hints: [web-auth, browser-session, cookie]
    - name: mobile
      hints: [mobile-token, device-auth, biometric]
    - name: service-to-service
      hints: [service-account, client-credentials, m2m]
```

## five_questions

```yaml
five_questions:
  - id: Q1
    question: How are tokens issued and what are their lifetimes?
    search_terms:
      - generateToken
      - issueToken
      - createSession
      - TokenResponse
      - expires_in
      - access_token
      - refresh_token
      - jwt
      - sign
  - id: Q2
    question: How are permissions and roles enforced at the service boundary?
    search_terms:
      - hasRole
      - hasPermission
      - @PreAuthorize
      - checkPermission
      - authorize
      - scope
      - role
      - policy
      - RBAC
      - ABAC
  - id: Q3
    question: How is session/token revocation propagated across services?
    search_terms:
      - revoke
      - invalidate
      - logout
      - blacklist
      - denylist
      - introspect
      - token.*revok
      - session.*destroy
  - id: Q4
    question: How does MFA / step-up authentication work?
    search_terms:
      - mfa
      - totp
      - otp
      - step.up
      - secondFactor
      - challenge
      - biometric
      - device.*verify
  - id: Q5
    question: How are third-party identity providers federated?
    search_terms:
      - saml
      - oidc
      - oauth
      - sso
      - federation
      - idp
      - assertion
      - sub.*claim
      - jwks
      - well-known
```

## critical_path_tiers

```yaml
critical_path_tiers:
  tier_0:
    label: Token issuance + validation
    definition: Issues tokens or validates them on every authenticated request
    provisional: []   # e.g., auth-service, token-service
  tier_1:
    label: Session store + JWKS
    definition: Required for token validation and revocation
    provisional: []   # e.g., session-store, jwks-endpoint-service
  tier_2:
    label: MFA + federation
    definition: Required for elevated auth flows and SSO
    provisional: []   # e.g., mfa-service, idp-gateway
  tier_3:
    label: Audit + rate-limiting
    definition: Auth observability and abuse prevention
    provisional: []   # e.g., audit-service, rate-limiter
  flow_critical_gates:
    - []   # e.g., token-service, permission-service
```

## deliverables

```yaml
deliverables:
  map_file: AUTH_MAP.md
  core_section: Token & Session Lifecycle
```

## ownership

```yaml
ownership:
  gitlab:
    org_prefix: ''          # fill in
    squad_path_segment: 2
    group_prefixes: []      # fill in
  datadog:
    service_aliases: {}
    domain_service_query: "name:auth*"
```

## architecture_validation

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: token-issuance-happy-path
      services: []    # fill in: e.g., [api-gateway, auth-service, token-service]
    - name: token-validation-path
      services: []    # fill in: e.g., [api-gateway, jwks-service]
    - name: revocation-propagation
      services: []    # fill in: e.g., [auth-service, session-store, dependent-services]
```

## Architecture signals to investigate

| Signal | What to determine |
|--------|-------------------|
| Token issuance | Which service signs — is there a dedicated token service or embedded auth? |
| JWKS rotation | How often keys rotate; is rotation zero-downtime? |
| Revocation store | Redis / DB / distributed cache — propagation delay |
| MFA bypass paths | Are there admin overrides or service-account exemptions? |
| Session vs stateless | Are sessions stored server-side or purely JWT-stateless? |

## Business flows (minimum 3 for P2)

Seed journeys for `BUSINESS_FLOWS.md`:

| Journey | Trigger | Terminal |
|---------|---------|----------|
| User login (password) | Credentials submitted | Access + refresh token issued |
| Token refresh | Refresh token presented | New access token or session expired |
| MFA step-up | High-risk action triggered | MFA verified or step-up denied |
| SSO / federation | IdP assertion received | Local session created |
| Logout / revocation | User logout or admin revoke | Token blacklisted, session destroyed |

## P3b adversarial hints

- **Token replay after revocation:** issue a token, revoke it, confirm it cannot be used on dependent services
- **Privilege escalation:** can a `user` role claim obtain a `admin` scope token?
- **JWKS rotation window:** is there a gap where old and new keys are both valid beyond the intended window?
- **Stale session after password reset:** confirm active tokens are revoked on password/credential change
- **Federation `sub` collision:** can two IdP users share the same `sub` claim after IdP migration?
