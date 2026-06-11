import { EVENT_BUS_NAME } from '@orcabus/platform-cdk-constructs/shared-config/event-bridge';
import path from 'path';
import { EVENT_SCHEMA_REGISTRY_NAME } from '@orcabus/platform-cdk-constructs/shared-config/event-bridge';
import { Duration, RemovalPolicy } from 'aws-cdk-lib';
import { SqsQueueName } from './sqs/interfaces';
import { GsiObject } from './dynamodb/interfaces';

/* Application dirs */
export const APP_ROOT = path.join(__dirname, '../../app');
export const LAMBDA_DIR = path.join(APP_ROOT, 'lambdas');
export const STEP_FUNCTIONS_DIR = path.join(APP_ROOT, 'step-functions-templates');
export const INTERFACE_DIR = path.join(APP_ROOT, 'interface');
export const EVENT_SCHEMAS_DIR = path.join(APP_ROOT, 'event-schemas');

/** Shared OrcaBus EventBridge bus name */
export const AWS_DEFAULT_EVENT_BUS = 'default'; // "default"
export const EVENT_BUS = EVENT_BUS_NAME; // "OrcaBusMain"

/* Database constants */
export const STACK_TABLE_NAME = 'DeployStatusStackTable';
export const EVENT_TABLE_NAME = 'DeployStatusEventTable';
export const EVENT_DATA_TABLE_INDEX_OBJS: GsiObject[] = [
  {
    indexName: 'latest-event',
    partitionKey: 'stack_name',
    sortKey: 'modification_timestamp',
  },
  {
    indexName: 'event-stack',
    partitionKey: 'stack_name',
  },
];
export const STACK_DATA_TABLE_INDEX_NAMES = [];
export const TABLE_REMOVAL_POLICY = RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE; // We need to retain the table on update or delete to avoid data loss

/* Event Constants */
export const API_VERSION = 'v1';
export const DEPLOY_STATUS_SUBDOMAIN_NAME = 'deploy-status';
export const STACK_PREFIX = 'deploy-status';
export const DEPLOY_STATUS_EVENT_DETAIL_TYPE = 'DeployStatusStateChange';

/* SQS / Lambda Constants */
export const SLACK_TOPIC_NAME = 'AwsChatBotTopic';
export const DEFAULT_EVENT_QUEUE_NAME: SqsQueueName = 'cloudFormationStateChangeSqsEventQueue';
export const DEFAULT_MAX_SQS_LAMBDA_CONCURRENCY = 10;
export const DEFAULT_SQS_LAMBDA_TIMEOUT = Duration.seconds(900);

/* SSM Constants */
export const SSM_PARAMETER_PATH_PREFIX = path.join(`/orcabus/deploy-status/`);

/* Schema constants */
export const SCHEMA_REGISTRY_NAME = EVENT_SCHEMA_REGISTRY_NAME;
export const SSM_SCHEMA_ROOT = path.join(SSM_PARAMETER_PATH_PREFIX, 'schemas');

/** Events this service listens to */
export const CLOUDFORMATION_STACK_STATUS_CHANGE_EVENT_DETAIL_TYPE =
  'CloudFormation Stack Status Change';
