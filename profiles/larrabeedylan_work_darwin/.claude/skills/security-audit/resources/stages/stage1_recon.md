# Stage 1 — Reconnaissance & Fingerprinting

Goal: understand exactly what this project **is** before deciding what to check for or how to attack it. Write `recon.md` as a precise, reasoned inventory — not a directory dump.

## Entry conditions

- `.security-audit/` exists and contains `recon.md` initialized from the template.
- `state.json.stage1.status` is `pending` or `in_progress`.

## Detection work

Read, do not guess. Use `Glob`, `Grep`, and selective `Read` — not recursive file dumps. For each fingerprint, cite the evidence (file path + line).

### Languages & runtimes
- Inspect `package.json`, `pyproject.toml`, `setup.py`, `requirements*.txt`, `Pipfile`, `poetry.lock`, `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`, `pom.xml`, `build.gradle*`, `*.csproj`, `*.fsproj`, `mix.exs`, `rebar.config`, `Package.swift`, `pubspec.yaml`, `*.podspec`, `Podfile`, `build.zig`, `Makefile`, `CMakeLists.txt`, `meson.build`, `BUILD.bazel`, `shard.yml`, `deno.json`, `bun.lockb`, `flake.nix`.
- Detect runtime versions from `.nvmrc`, `.tool-versions`, `.python-version`, `.ruby-version`, `go.mod` go directive, `rust-toolchain.toml`, Dockerfile base images.

### Frameworks (examples — extend as needed)
- **Web/API**: Express/Fastify/NestJS/Next.js/Nuxt/Remix/SvelteKit, Django/Flask/FastAPI/Starlette, Rails/Sinatra/Hanami, Phoenix, Spring Boot/Quarkus/Micronaut, ASP.NET Core, Laravel/Symfony, Gin/Echo/Fiber/Chi, Actix/Axum/Rocket.
- **Mobile**: UIKit/SwiftUI, Jetpack Compose/legacy Android, React Native, Flutter, Capacitor/Cordova, Xamarin/MAUI.
- **Desktop**: Electron, Tauri, Qt, WPF, Cocoa, GTK.
- **IaC**: Terraform, OpenTofu, Pulumi, CloudFormation, CDK, Ansible, Chef, Puppet, Helm, Kustomize, Kubernetes manifests, Docker Compose.
- **LLM**: LangChain, LlamaIndex, Haystack, Semantic Kernel, Guidance, raw SDKs (`openai`, `anthropic`, `google-generativeai`, `litellm`, `instructor`), vector stores (`pinecone`, `weaviate`, `qdrant`, `pgvector`, `chroma`), MCP servers.
- **Smart contracts**: Hardhat, Foundry, Truffle, Brownie, Ape, Anchor (Solana), CosmWasm, Near-SDK, Ink!.
- **Data**: Airflow, Dagster, Prefect, dbt, Spark, Beam, Kafka Streams, Flink.
- **Firmware**: Zephyr, FreeRTOS, ESP-IDF, STM32Cube, Yocto, bare-metal with linker scripts.

### Build & packaging
- Build systems and their config (Webpack, Vite, esbuild, Rollup, Turbopack, Parcel, Rome/Biome; Maven, Gradle, sbt; Bazel, Buck, Pants).
- Package managers (npm/pnpm/yarn/bun; pip/poetry/uv/conda/pipenv; cargo; go modules; maven/gradle; composer; nuget).
- Lockfile presence and integrity signals.
- Monorepo tooling (Nx, Turborepo, Rush, Lerna, Moon, Pants).

### Deployment & runtime targets
- `Dockerfile*`, `docker-compose*.yml`, `.dockerignore`, Podman/OCI variants.
- Kubernetes manifests (`k8s/**/*.yaml`, Helm charts, Kustomize overlays, CRDs).
- Serverless (Lambda/`serverless.yml`/SAM, Cloud Functions, Azure Functions, Cloudflare Workers `wrangler.toml`, Deno Deploy, Vercel, Netlify).
- Platform-as-a-service config (`Procfile`, `fly.toml`, `render.yaml`, `railway.json`, `app.yaml`).
- Edge/CDN config (Cloudflare, Fastly VCL, Akamai EdgeWorkers, Workers KV/D1/R2 bindings).
- Bare metal hints: systemd units, `init.d`, `/etc/` references in repo scripts.

### Authn / authz
Identify patterns by grepping for markers, not by assumption:
- Sessions (cookie names, store backend), JWT (library, signing alg), OAuth/OIDC (client config, flow — code/implicit/PKCE/client-credentials/device), SAML, mTLS, API keys (header conventions, storage), HMAC-signed requests, request-signing (AWS SigV4-style), WebAuthn/passkeys, magic links, password reset flows, MFA implementation.
- Role/permission definitions: RBAC tables, policy-as-code (OPA/Rego, Cedar), ABAC attribute sources.

### Data stores
- SQL drivers and ORMs, migration tooling (Flyway, Liquibase, Alembic, Prisma, TypeORM, Ecto, ActiveRecord).
- NoSQL/KV/object (Mongo, Redis, DynamoDB, Cassandra, S3/GCS/Azure Blob, SQLite/Turso/DuckDB).
- Search (Elasticsearch, OpenSearch, Meilisearch, Typesense, Algolia).
- Queues/streaming (SQS, SNS, Kafka, RabbitMQ, NATS, Pub/Sub, Kinesis, Redis Streams, BullMQ, Sidekiq, Celery).
- Cache layers (Redis, Memcached, in-process LRUs).

### External integrations
- HTTP clients (grep for domains, tokens, webhook secrets).
- Third-party SDKs (Stripe, Twilio, SendGrid, Auth0/Clerk/Cognito/Firebase, AWS/GCP/Azure SDKs).
- Webhooks (signature verification presence is mandatory to note).

### Protocols & formats
- HTTP (1.1/2/3), WebSocket, SSE, gRPC (proto files, reflection on/off), GraphQL (SDL files, introspection setting), Thrift, MessagePack, Protobuf, Avro, CBOR, Cap'n Proto.
- Template engines (Jinja, Twig, ERB, EJS, Handlebars, Liquid, Pug, Mustache, Blade, Razor, Freemarker, Velocity, Tera, Askama).
- Serialization (pickle, cloudpickle, Marshal, BinaryFormatter, `node-serialize`, YAML with `!!python/object` tags, JSON-with-types like Jackson default typing).

### Entry points & surface
Enumerate every externally reachable input path:
- HTTP routes (parse router files; for dynamic routers, list registrations).
- CLI commands/subcommands and their argument parsers.
- Event/handler registrations (queue consumers, cron/schedulers, webhook receivers, event-bus subscribers, signal handlers, IPC endpoints, Unix domain sockets, named pipes).
- Public library functions (exports in `index.ts`, `__init__.py`, `lib.rs`, package exports).
- Browser extension message handlers, content-script injection targets.
- Mobile deep links, intent filters, URL schemes, app-links.
- Smart contract external/public functions, receive/fallback handlers.
- Hardware interfaces (JTAG/SWD, UART, USB, Bluetooth/BLE services, Wi-Fi AP mode).

For each entry point, capture:
- Path/name
- Auth requirement (none / authenticated / role-gated — cite the enforcement location)
- Accepts which inputs (body, headers, query, path, file upload)
- Downstream sinks touched (db, fs, shell, network, template render, deserializer)

### Trust boundaries
Draw the boundaries explicitly. Each crossing is a risk. Examples:
- Untrusted user → application
- Application → database (is input parameterized?)
- Application → shell/process (is input shell-escaped?)
- Application → file system (is path validated?)
- Application → external HTTP (SSRF candidate?)
- Client-side state → server trust (never trust client totals/prices/roles)
- Tenant A → tenant B (how is isolation enforced?)

### CI/CD & observability
- CI config (GitHub Actions, GitLab CI, CircleCI, Buildkite, Jenkinsfile, Azure Pipelines, Drone, Woodpecker).
- Registry usage, signing (cosign, notary, SLSA provenance).
- Secrets management (Vault, SOPS, sealed-secrets, doppler, AWS SM, GCP SM, `.env` patterns).
- Observability (OpenTelemetry, Sentry, Datadog, New Relic, Honeycomb, Grafana, Prometheus).

## Writing `recon.md`

Use the template sections already present. Keep entries short, linkable, and evidence-backed:

- Project summary (≤ 5 lines): what it is, what it promises to do, who talks to it.
- Project classification: pick one or more of `web | api | cli | library | iac | mobile | desktop | embedded | ml-llm | browser-ext | smart-contract | data-pipeline | hybrid`. This selection drives which methodology files to load.
- Languages & versions.
- Frameworks & key libraries (highlight security-relevant ones: auth, crypto, template, HTTP clients, deserializers, file handlers).
- Dependency graph highlights (direct count, transitive count, known-CVE count if `osv-scanner` or equivalent was run).
- Deployment targets.
- Authn/authz summary.
- Data stores and what each holds (PII? secrets? tenancy-scoped?).
- External integrations (redact tokens).
- Entry point inventory table: `Path | Auth | Inputs | Sinks | Notes`.
- Trust boundary map.
- Observations about the project that will shape threat modeling (e.g. "no rate limiting visible", "admin routes behind same auth as user routes", "crypto rolled by hand in `utils/crypto.ts`").

At the end of `recon.md`, list the methodology files to load for Stage 2+:
```
Methodology files to apply: generic.md, web.md, api.md, supply-chain.md, crypto.md
```

Update `state.json.stage1` to `completed` with `detected_classes`, `timestamp`, and tool versions (for any scanners run in recon — e.g. `syft` for SBOM).

## Common mistakes

- Listing every file rather than every attack surface.
- Trusting `package.json` over actual imports (dead deps and missing deps both happen).
- Conflating "uses OAuth" with "OAuth is correctly implemented" — recon names the pattern, threat model questions it, static audit verifies it.
- Missing background surface (cron, queue consumers, startup hooks, signal handlers) because they aren't in the router.
- Assuming middleware enforces auth globally without checking every handler.
