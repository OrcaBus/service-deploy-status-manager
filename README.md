Service Deploy Status Manager
================================================================================

- [Hello World Service](#hello-world-service)
  - [New Here? Start Here](#new-here-start-here)
  - [Using This Template](#using-this-template)
    - [1. Rename the service](#1-rename-the-service)
    - [2. Wire up the stateless pipeline](#2-wire-up-the-stateless-pipeline)
    - [3. Decide on stateful infrastructure](#3-decide-on-stateful-infrastructure)
    - [4. Replace the Lambda logic](#4-replace-the-lambda-logic)
    - [5. Update tests](#5-update-tests)
    - [6. Update this README](#6-update-this-readme)
  - [Service Description](#service-description)
    - [Name \& responsibility](#name--responsibility)
    - [Description](#description)
    - [API Endpoints](#api-endpoints)
    - [Consumed Events](#consumed-events)
    - [Published Events](#published-events)
    - [(Internal) Data states \& persistence model](#internal-data-states--persistence-model)
    - [Major Business Rules](#major-business-rules)
    - [Permissions \& Access Control](#permissions--access-control)
    - [Change Management](#change-management)
      - [Versioning strategy](#versioning-strategy)
      - [Release management](#release-management)
  - [Infrastructure \& Deployment](#infrastructure--deployment)
    - [Stateful](#stateful)
    - [Stateless](#stateless)
    - [CDK Commands](#cdk-commands)
    - [Stacks](#stacks)
  - [Development](#development)
    - [Project Structure](#project-structure)
    - [Setup](#setup)
      - [Requirements](#requirements)
      - [Install Dependencies](#install-dependencies)
      - [First Steps](#first-steps)
    - [Conventions](#conventions)
    - [Linting \& Formatting](#linting--formatting)
    - [Testing](#testing)
  - [Glossary \& References](#glossary--references)


Description
--------------------------------------------------------------------------------

This service is set up to track deployments of microservices across the OrcaBus.
Head to the API endpoint [https://deploy-status.umccr.org](https://deploy-status.umccr.org) to see the current deployment status of all services being tracked by this service.

CloudFormation automatically sends events to EventBridge on stack creation, update, and deletion.
By filtering for these events, this service can maintain an up-to-date inventory of all
deployed services, their versions, and deployment status.

In order to ensure that your microservice is tracked by this service,
your application stack will need to be an extension of `GitStack`.
The following shows an example of an application stack that follows this logic:

```ts
// Available in @orcabus/platform-cdk-constructs version 1.7.0 or higher
import { GitStack } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';

// Your stack config
export type StatelessApplicationStackProps = StatelessApplicationStackConfig & cdk.StackProps;

// Application Stack
export class ApplicationStack extends GitStack {
  public readonly stageName: StageName;
  constructor(scope: Construct, id: string, props: StatelessApplicationStackProps) {
    super(scope, id, props);
    // your stack code as normal
  }
}
```

You will need to do this for both your stateless and stateful stacks (if applicable).

### API Endpoints

This service has the following GET API endpoints which can be used to query the deployment status of services across the OrcaBus.

* `/api/v1/deployStatus/listStacks`  - List all stacks in the registry
* `/api/v1/deployStatus/getAllStacksSummary` - Return a summary of all stacks and their most recent cloud formation events
* `/api/v1/deployStatus/{stackId}/latest` - Returns the latest deployment status for the specified stack ID, including the:
  * stackName
  * gitCommitId,
  * deployStatus (e.g., `CREATE_COMPLETE`, `UPDATE_IN_PROGRESS`), and
  * modificationTimeStamp
* `/api/v1/deployStatus/{stackId}/events` - Returns a paginated history of deployment events for the specified stack ID, including the same details as above for each event.
* `/api/v1/deployStatus/{stackId}/events/{eventId}` - Returns details for a specific deployment event, identified by `eventId`.

We have one POST endpoint (for internal service-use only and hidden from view):

* `/api/v1/deployStatus/addStackEvent`
  * This endpoint is used internally by the service to add a new deployment event to the service's data store.
  * It is not intended for external use. The endpoint accepts a JSON payload with the following structure:
  ```json
  {
    "stackId": "string",
    "stackName": "string",
    "eventId": "string",
    "stackStatus": "string",
    "gitCommitId": "string",
    "modificationTimestamp": "string"
  }
  ```

### Consumed Events

Consumes CloudFormation events from default AWS eventbus.

### Published Events

| Name / DetailType  | Source                        | Schema Link                                                                      | Description                                                       |
|--------------------|-------------------------------|----------------------------------------------------------------------------------|-------------------------------------------------------------------|
| `StackStateChange` | `orcabus.deploystatusmanager` | [StackStateChange](/app/event-schemas/stack-state-change/2026.06.04/schema.json) | Emitted after successfully processing a stack state change event. |

### (Internal) Data states & persistence model

We use a dynamodb table to store the deployment status of all stacks being tracked by the service.
Each item in the table represents a deployment event for a specific stack.

#### Release management

The service employs a fully automated CI/CD pipeline that automatically builds and releases all changes to the `main` branch
across `beta`, `gamma`, and `prod` environments.


Infrastructure & Deployment
--------------------------------------------------------------------------------

Infrastructure is managed via CDK. This template provides two types of CDK entry points: `cdk-stateless` and `cdk-stateful`.

### Stateful

- **`DeployStatusStackTable`** - DynamoDb table with the status orcabus id as the partition key and no sort key
- **`DeployStatusEventTable`** - DynamoDb table with the event orcabus id as the partition key and stack name as the sort key.
- **`DeployStatusSqsQueue`** - SQS queue used as a dead letter queue for failed events that could not be processed and stored in the DynamoDB table.
  - This ensures that we do not lose any deployment events and can investigate and reprocess failed events as needed.

### Stateless

**Non SFN Lambdas**

- **`DeployStatusApi`** - API Gateway REST API with Lambda integration.
  - This API exposes the endpoints described in the Service Description section above, allowing clients to query the deployment status of services across the OrcaBus.
  - The API is also responsible for emitting `StackStateChange` events to EventBridge after successfully processing deployment events and updating the DynamoDB table.
- **`DeployStatusEventHandler`** - Use a Durable Lambda function to process incoming CloudFormation events from EventBridge, extract relevant information, and store it in the DynamoDB table.
  - The event handler then calls AWS Step Functions to orchestrate the processing of the event, including any necessary retries and error handling

**Step Functions**

- **`AddCfEventToSqsQueue`** - Because our event rules are in a different stack to our sqs queue, we have to use another service to parse
    data between the rule and the queue.

- **`ProcessCfEvent`** - Step Functions state machine that processes deployment events.
  - This state machine is triggered by the `DeployStatusEventHandler` Lambda function and is responsible for orchestrating the processing of deployment events, including any necessary retries and error handling.
  - Using Step Functions allows us to manage complex event processing logic and ensure that events are processed reliably, even in the face of transient errors or failures.
  - We call the following lambdas inside the AWS Step Functions:
    - Add stack event to DynamoDB table via the API endpoint (`/addStackEvent`)
    - Using the callbackId from the DeployStatusEventHandler lambda, we can release the event handler from waiting allowing it to process the next event.

**EventBridge**

- **`CloudFormationEventRule`** - EventBridge rule that filters for CloudFormation events related to stack creation, update, and deletion.
  - This rule triggers the `DeployStatusEventHandler` Lambda function whenever a relevant CloudFormation event occurs, ensuring that the service maintains an up-to-date inventory of all deployed services and their deployment status.


### CDK Commands

You can access CDK commands using the `pnpm` wrapper script.

- **`cdk-stateless`**: Used to deploy stacks containing stateless resources (e.g., AWS Lambda), which can be easily redeployed without side effects.
- **`cdk-stateful`**: Used to deploy stacks containing stateful resources (e.g., AWS DynamoDB, AWS RDS), where redeployment may not be ideal due to potential side effects.

The type of stack to deploy is determined by the context set in the `./bin/deploy.ts` file.

You can list all available stacks using:

```sh
pnpm cdk-stateful list
```

```
DeployStatusStatefulDeployStack
DeployStatusStatefulDeployStack/DeployStatusStatefulDeployPipeline/OrcaBusBeta/DeployStatusStatefulDeployStack (OrcaBusBeta-DeployStatusStatefulDeployStack)
DeployStatusStatefulDeployStack/DeployStatusStatefulDeployPipeline/OrcaBusGamma/DeployStatusStatefulDeployStack (OrcaBusGamma-DeployStatusStatefulDeployStack)
DeployStatusStatefulDeployStack/DeployStatusStatefulDeployPipeline/OrcaBusProd/DeployStatusStatefulDeployStack (OrcaBusProd-DeployStatusStatefulDeployStack)
```

```sh
pnpm cdk-stateless list
```

```
DeployStatusStatelessDeployStack
DeployStatusStatelessDeployStack/DeployStatusStatelessDeploymentPipeline/OrcaBusBeta/DeployStatusStatelessDeployStack (OrcaBusBeta-DeployStatusStatelessDeployStack)
DeployStatusStatelessDeployStack/DeployStatusStatelessDeploymentPipeline/OrcaBusGamma/DeployStatusStatelessDeployStack (OrcaBusGamma-DeployStatusStatelessDeployStack)
DeployStatusStatelessDeployStack/DeployStatusStatelessDeploymentPipeline/OrcaBusProd/DeployStatusStatelessDeployStack (OrcaBusProd-DeployStatusStatelessDeployStack)
```

Development
--------------------------------------------------------------------------------

### Project Structure

The root of the project is an AWS CDK project where the main application logic lives inside the `./app` folder.

The project is organized into the following key directories:

- **`./app`**: Contains the main application logic. You can open the code editor directly in this folder, and the application should run independently.

- **`./bin/deploy.ts`**: Serves as the entry point of the application. It initializes two root stacks: `stateless` and `stateful`. You can remove one of these if your service does not require it.

- **`./infrastructure`**: Contains the infrastructure code for the project:
  - **`./infrastructure/toolchain`**: Includes stacks for the stateless and stateful resources deployed in the toolchain account. These stacks primarily set up the CodePipeline for cross-environment deployments.
  - **`./infrastructure/stage`**: Defines the stage stacks for different environments:
    - **`./infrastructure/stage/config.ts`**: Contains environment-specific configuration files (e.g., `beta`, `gamma`, `prod`).
    - **`./infrastructure/stage/stateless-application-stack.ts`**: The stateless CDK stack entry point for provisioning resources required by the application in `./app`.
    - **`./infrastructure/stage/stateful-application-stack.ts`**: The stateful CDK stack entry point for provisioning resources required by the application in `./app`.

- **`.github/workflows/pr-tests.yml`**: Configures GitHub Actions to run tests for `make check` (linting and code style), tests defined in `./test`, and `make test` for the `./app` directory. Modify this file as needed to ensure the tests are properly configured for your environment.

- **`./test`**: Contains tests for CDK code compliance against `cdk-nag`. You should modify these test files to match the resources defined in the `./infrastructure` folder.

### Setup

#### Requirements

```sh
node --version
v22.9.0

# Update Corepack (if necessary, as per pnpm documentation)
npm install --global corepack@latest

# Enable Corepack to use pnpm
corepack enable pnpm
```

#### Install Dependencies

To install all required dependencies, run:

```sh
make install
```

### Conventions

### Linting & Formatting

Automated checks are enforced via pre-commit hooks, ensuring only checked code is committed. For details consult the `.pre-commit-config.yaml` file.

Manual, on-demand checking is also available via `make` targets. For details consult the `Makefile` in the root of the project.

To run linting and formatting checks on the root project, use:

```sh
make check
```

To automatically fix issues with ESLint and Prettier, run:

```sh
make fix
```

### Testing

Unit tests are available for the Lambda handler and Pydantic models. Test code is hosted alongside business logic in `./app/tests/`.

```sh
# CDK infrastructure tests
pnpm test
```

> **Note:** The CDK tests synthesize the Lambda layer using Docker. If Docker is not running, `pnpm test` will fail with `Cannot connect to the Docker daemon`. Start Docker Desktop before running CDK tests locally.


Glossary & References
--------------------------------------------------------------------------------

For general terms and expressions used across OrcaBus services, please see the platform [documentation](https://github.com/OrcaBus/wiki/blob/main/orcabus-platform/README.md#glossary--references).
