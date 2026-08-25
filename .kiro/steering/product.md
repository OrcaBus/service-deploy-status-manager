# Product: Deploy Status Manager

## Overview

The Deploy Status Manager is a microservice within the OrcaBus platform that tracks and reports deployment status of all OrcaBus microservices. It monitors CloudFormation stack events to maintain a real-time inventory of deployed services, their versions (git commit IDs), and current deployment state.

## Domain

- **Organization**: University of Melbourne Centre for Cancer Research (UMCCR)
- **Platform**: OrcaBus — a suite of bioinformatics orchestration microservices
- **URL**: https://deploy-status.umccr.org

## Core Functionality

1. **Event Ingestion** — Consumes CloudFormation stack status change events from the AWS default EventBridge bus.
2. **Event Processing** — Uses a durable Lambda + Step Functions pipeline to reliably process and store deployment events in DynamoDB.
3. **REST API** — Exposes a FastAPI-based read API to query stack statuses, event histories, and deployment summaries.
4. **Event Publication** — Emits `StackStateChange` events (source: `orcabus.deploystatusmanager`) to the OrcaBus event bus after processing.

## Key Concepts

- **Stack**: A tracked CloudFormation stack. Identified by an OrcaBus ID with prefix `cfs`.
- **Event**: A single CloudFormation status change for a stack. Identified by an OrcaBus ID with prefix `cfe`.
- **OrcaBus ID**: A prefixed ULID (e.g., `cfs.01ARZ3NDEKTSV4RRFFQ69G5FAV`). The ULID encodes creation time for natural ordering.
- **GitStack**: Services must extend `GitStack` from `@orcabus/platform-cdk-constructs` to be tracked.

## Environments

Deploys across three stages via CodePipeline: `beta` → `gamma` → `prod`.
