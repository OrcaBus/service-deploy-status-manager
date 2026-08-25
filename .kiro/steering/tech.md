# Tech Stack & Build System

## Languages

- **TypeScript** — Infrastructure as Code (CDK stacks, toolchain, tests)
- **Python** — Application logic (Lambda handlers, FastAPI interface)

## Infrastructure (TypeScript)

| Tool / Library | Purpose |
|---|---|
| AWS CDK (`aws-cdk-lib` 2.258.x) | Infrastructure as Code |
| `@aws-cdk/aws-lambda-python-alpha` | Python Lambda bundling |
| `@orcabus/platform-cdk-constructs` | Shared OrcaBus CDK constructs (GitStack, API Gateway config, event bus config) |
| `cdk-nag` | CDK compliance / security checks |
| `sqs-dlq-monitoring` | SQS dead-letter queue monitoring |

## Application (Python)

| Library | Purpose |
|---|---|
| FastAPI | REST API framework |
| Mangum | AWS Lambda adapter for ASGI (FastAPI → Lambda) |
| Pydantic | Data validation and serialization |
| Dyntastic | DynamoDB ORM built on Pydantic |
| `fastapi_tools` | Shared pagination utilities (Lambda layer) |
| `aws-durable-execution-sdk-python` | Durable Lambda execution with callback support |
| boto3 | AWS SDK for Python |

## Package Management

- **Node/TypeScript**: pnpm (version 11.5.3, enforced via `corepack`)
- **Python**: Dependencies per-Lambda in `requirements.txt` files; shared code via Lambda layers
- **Node version**: 22.x+ (24.x in CI)

## Linting & Formatting

| Tool | Scope | Config |
|---|---|---|
| ESLint (v10, flat config) | TypeScript/JS (`eslint.config.mjs`) | `app/` excluded — has own config |
| Prettier | All files (`.prettierrc.json`) | 100 char width, single quotes, 2-space indent, trailing comma es5 |
| pre-commit | Git hooks (`.pre-commit-config.yaml`) | Runs: large file check, YAML check, AWS cred detection, secret detection, ESLint, Prettier |
| detect-secrets | Secret scanning | Baseline in `.secrets.baseline` |

## Testing

- **CDK tests**: Jest + ts-jest, run via `pnpm test` (synthesizes stacks, validates with cdk-nag)
- **CDK tests require Docker** for Python Lambda layer synthesis
- **Python tests**: Referenced in README but test directory is in `./app/tests/` (unit tests for handler and models)

## AWS Services Used

- DynamoDB (two tables: stacks + events)
- Lambda (Python runtime)
- Step Functions (event processing orchestration)
- EventBridge (event ingestion + publication)
- SQS (dead-letter queue for failed events)
- API Gateway HTTP API (with Cognito auth)
- CodePipeline (CI/CD across environments)

## Common Commands

```sh
# Install all dependencies
make install

# Run linting + formatting checks
make check

# Auto-fix lint + formatting issues
make fix

# Run CDK infrastructure tests (requires Docker)
pnpm test

# List stateless CDK stacks
pnpm cdk-stateless list

# List stateful CDK stacks
pnpm cdk-stateful list

# Synth a stateless stack
pnpm cdk-stateless synth

# Synth a stateful stack
pnpm cdk-stateful synth

# Deploy (use cdk-stateless or cdk-stateful)
pnpm cdk-stateless deploy <StackName>
```

## CI/CD

- **PR checks** (GitHub Actions): pre-commit lint/security scan + CDK test synthesis
- **Deployment**: Automated via CodePipeline on merge to `main` → beta → gamma → prod
