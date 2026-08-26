# Project Structure

## Top-Level Layout

```
.
├── app/                        # Application logic (Python)
├── bin/                        # CDK app entry point
│   └── deploy.ts              # Initializes stateful or stateless stack based on context
├── infrastructure/             # CDK infrastructure code (TypeScript)
│   ├── stage/                 # Per-environment stack definitions
│   └── toolchain/             # CodePipeline toolchain stacks
├── test/                       # CDK infrastructure tests (Jest)
├── docs/                       # Documentation
├── scratch/                    # Scratch/experimental files
├── .github/workflows/          # GitHub Actions CI
├── cdk.json                    # CDK app configuration
├── package.json                # Node dependencies & scripts
├── tsconfig.json               # TypeScript config
├── Makefile                    # Top-level build/check/fix commands
├── eslint.config.mjs           # ESLint flat config
├── .prettierrc.json            # Prettier config
└── .pre-commit-config.yaml     # Pre-commit hooks
```

## `app/` — Application Logic (Python)

All Python application code lives here. Each Lambda has its own subdirectory with a handler file and optional `requirements.txt`.

```
app/
├── interface/                  # API Lambda (FastAPI)
│   ├── handler.py             # FastAPI app + Mangum adapter (Lambda entry point)
│   └── deploy_status_api/     # API package
│       ├── api/v1/            # Versioned route definitions
│       │   └── deploy_status.py  # All REST endpoints
│       ├── models/            # Pydantic/Dyntastic models
│       │   ├── event.py       # EventData DynamoDB model
│       │   ├── stack.py       # StackData DynamoDB model
│       │   ├── event_query.py # Event query parameters
│       │   ├── stack_query.py # Stack query parameters
│       │   ├── stack_event.py # POST event schema
│       │   └── stack_summary.py # Summary response type
│       ├── events/            # EventBridge event publishing
│       │   └── events.py
│       ├── globals.py         # Constants, regex patterns, env var names
│       └── utils.py           # Shared utilities
├── lambdas/                    # Non-API Lambda handlers
│   ├── add_stack_event_py/
│   ├── get_commit_id_from_stack_py/
│   ├── get_event_id_and_timestamp_py/
│   ├── get_stack_orcabus_id_py/
│   ├── handle_deploy_status_sqs_py/    # Durable execution Lambda (SQS consumer)
│   └── update_callback_py/             # Step Functions callback handler
├── event-schemas/              # Published event JSON schemas
│   └── stack-state-change/2026.06.04/schema.json
└── step-functions-templates/   # Step Functions ASL definitions
    ├── add_cf_event_to_sqs_queue_sfn_template.asl.json
    └── process_cf_event_sfn_template.asl.json
```

## `infrastructure/` — CDK Stacks (TypeScript)

```
infrastructure/
├── stage/                      # Application stacks deployed per environment
│   ├── config.ts              # Environment-specific configuration
│   ├── constants.ts           # Shared constants (table names, prefixes, etc.)
│   ├── interfaces.ts          # TypeScript interfaces for stack props
│   ├── stateful-application-stack.ts   # DynamoDB tables, SQS queue
│   ├── stateless-application-stack.ts  # Lambdas, API Gateway, Step Functions, EventBridge
│   ├── api/                   # API Gateway construct
│   ├── dynamodb/              # DynamoDB table constructs
│   ├── event-rules/           # EventBridge rule constructs
│   ├── event-schemas/         # EventBridge schema constructs
│   ├── event-targets/         # EventBridge target constructs
│   ├── lambda/                # Lambda function constructs
│   ├── sqs/                   # SQS queue constructs
│   ├── step-functions/        # Step Functions constructs
│   └── utils/                 # CDK utility helpers
└── toolchain/                  # Pipeline stacks (deployed to toolchain account)
    ├── constants.ts
    ├── stateful-stack.ts      # CodePipeline for stateful resources
    └── stateless-stack.ts     # CodePipeline for stateless resources
```

## `test/` — CDK Tests

```
test/
├── stage.test.ts              # cdk-nag compliance tests for stage stacks
├── toolchain.test.ts          # cdk-nag compliance tests for toolchain stacks
└── utils.ts                   # Test utilities
```

## Conventions

- **Lambda naming**: Each Lambda directory is named `<function_name>_py/` and contains a Python file matching the function name.
- **Stateful vs Stateless**: Infrastructure is split into two CDK apps. Stateful holds persistent resources (DynamoDB, SQS). Stateless holds compute and routing (Lambda, API GW, Step Functions, EventBridge rules).
- **API versioning**: Routes are namespaced under `/api/v1/` with versioned directories in the code (`api/v1/`).
- **Models**: Each DynamoDB entity has a Pydantic model (for validation) that extends `Dyntastic` (for DynamoDB ORM). Response types use `TypedDict` for strict typing.
- **camelCase API responses**: Python models use `snake_case` internally but serialize to `camelCase` via Pydantic `alias_generator=to_camel`.
- **OrcaBus IDs**: All entities use prefixed ULIDs (e.g., `cfs.`, `cfe.`) generated from timestamps for natural sort ordering.
