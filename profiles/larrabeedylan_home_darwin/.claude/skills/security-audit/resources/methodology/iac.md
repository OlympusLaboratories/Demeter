# Infrastructure-as-Code methodology

Loaded for `iac` project class (Terraform, Pulumi, CloudFormation, CDK, Helm, Kustomize, K8s manifests, Ansible, Chef, Puppet, Docker Compose).

## AWS — common findings

### S3
- `acl = "public-read"` or `"public-read-write"` on buckets meant to be private.
- Missing `aws_s3_bucket_public_access_block` resource with all four `block_*` set to true.
- Missing server-side encryption (`aws_s3_bucket_server_side_encryption_configuration`).
- Missing versioning for critical data.
- Missing access logging.
- Presigned URL generation with excessive TTL.
- Bucket policy `"Principal": "*"` without explicit constraint.

### IAM
- Policies with `Action: "*"` on `Resource: "*"`.
- `iam:PassRole` without a `Condition` restricting target roles.
- Role trust policies with broad principals (`"AWS": "*"`) or with SAML/OIDC issuer conditions that are spoofable.
- Long-lived access keys instead of roles.
- Inline policies that shadow managed policy reviews.
- `sts:AssumeRole` trust allowing any external account.

### RDS / databases
- `publicly_accessible = true`.
- `storage_encrypted = false`.
- `backup_retention_period = 0`.
- `deletion_protection = false` for prod.
- Parameter groups allowing weak TLS versions.
- Security group allowing `0.0.0.0/0` on database port.

### EC2 / Security groups
- SG ingress `0.0.0.0/0` on non-public ports (22, 3389, 3306, 5432, 6379, 27017, 9200, 11211, 9092...).
- IMDSv1 enabled (`metadata_options.http_tokens = "optional"`) — require `"required"` for IMDSv2.
- Missing default tags (complicates incident response).
- Public AMI sharing unintended.

### Lambda / serverless
- Environment variables contain secrets in plaintext (prefer SSM/Secrets Manager with KMS).
- `*` resource in IAM execution role.
- Function URL with `AuthType: NONE` for anything non-public.
- No VPC config when the function accesses private resources (then it goes via NAT — may or may not be intended; document).

### KMS
- Key policies with `*` principals.
- Key rotation disabled for CMK.
- Grant to cross-account role without scoping.

### Networking
- VPC flow logs disabled.
- NACLs not restricting internal traffic.
- Default VPC used for workloads (lazy).
- NAT gateway / VPC endpoints not used for AWS-service egress (bill leak + traffic crosses Internet).

## GCP — common findings

- Cloud Storage buckets with `allUsers`/`allAuthenticatedUsers` principals on any role other than explicit public-asset serving.
- Compute instances with default service account + broad scopes.
- BigQuery datasets shared to `allUsers`.
- IAM bindings at project level where per-resource binding suffices.
- Logging / monitoring not enabled.

## Azure — common findings

- Storage accounts with anonymous blob access.
- SQL Server firewall rule `0.0.0.0`–`255.255.255.255`.
- Managed identities with Owner/Contributor scope.
- Key Vault: missing soft-delete + purge protection; missing access policy restrictions.
- Network Security Group rules allowing broad inbound.

## Kubernetes manifests

### Pod security
- `securityContext.runAsNonRoot: true` absent.
- `runAsUser: 0` present.
- `allowPrivilegeEscalation: true` or absent (default).
- `readOnlyRootFilesystem: false` where compatible.
- `privileged: true`.
- Capabilities added: `SYS_ADMIN`, `NET_ADMIN`, `SYS_PTRACE`, `DAC_OVERRIDE`.
- Default `capabilities.drop: ["ALL"]` missing.

### Pod spec
- `hostNetwork`, `hostPID`, `hostIPC` set to true.
- `hostPath` volume mounts (especially `/` or `/etc` or docker socket `/var/run/docker.sock`).
- `automountServiceAccountToken: true` where the workload doesn't use the API.
- Missing resource requests/limits (can be weaponized for DoS via cluster exhaustion).
- Missing readiness/liveness probes (indirect reliability issue).

### Cluster-wide
- Namespaces without NetworkPolicy — default allow-all between pods.
- PodSecurity admission level `privileged` for non-system namespaces (prefer `baseline` or `restricted`).
- RBAC: `cluster-admin` bindings to human users.
- Tiller / legacy components.
- Secrets stored as `Secret` (base64, not encrypted by default) without `--encryption-provider-config` on etcd.
- Ingress with weak TLS or no TLS.
- API server with anonymous auth enabled.

### Helm
- Values files checked into public repos containing references to prod endpoints.
- Default values expose admin passwords.
- Chart `{{ .Values.X | nindent }}` string-concat into command (shell injection at render time).

## Terraform / OpenTofu specifics

- `sensitive = true` missing on variables holding secrets.
- State files stored in S3 without encryption or without DynamoDB locking.
- Local-exec provisioners running attacker-influenced strings.
- Module sources pulled from Git without commit pinning (`source = "github.com/foo/bar"` without `?ref=<sha>`).
- `terraform plan` output containing secrets (logs on CI).
- Checked-in `.tfstate` or `.tfstate.backup` in VCS.

## CloudFormation / CDK

- Parameters with defaults that include secrets.
- `DynamicReference` without a deny policy if upstream SSM/SecretsManager is permissive.
- `!Ref` into policies that doesn't scope.
- CDK: escape hatches that override generated safer defaults.

## Ansible / Chef / Puppet

- `no_log: true` missing on tasks that handle secrets → logs leak.
- `become: yes` blanket at play level.
- Files deployed 0777.
- Git-based source with no integrity check.
- `include_vars` pulling from attacker-controllable location.

## Docker Compose

- `privileged: true`.
- Volume mount of docker socket.
- `network_mode: host`.
- `pid: host`.
- `env_file` committed.
- `ports: - "0.0.0.0:5432:5432"` exposing DB publicly.

## Tool recipe

- `checkov -d . --framework terraform,kubernetes,docker,cloudformation,helm,ansible --output json`
- `tfsec . --format json`
- `trivy config .`
- `kics scan -p . -o .security-audit/tool-logs/`
- `kube-linter lint .`
- `polaris audit --audit-path .`
- `hadolint Dockerfile*`
- `dockle <built-image>`

Review findings with the same triage discipline as code SAST: confirm reachability and impact before promoting.

## Secrets in IaC

- Any `password = "..."`, `api_key = "..."`, `token = "..."` inline value is a finding.
- `data "aws_secretsmanager_secret_version"` is fine; `variable "db_password" { default = "…" }` is not.
- `locals` with secrets is not; move to SSM/Vault/Secrets Manager.
- CI pipelines setting `TF_VAR_db_password` from repo-stored vault is fine; plaintext in the repo is not.
