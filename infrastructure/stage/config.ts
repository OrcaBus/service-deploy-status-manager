import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import {
  AWS_DEFAULT_EVENT_BUS,
  CLOUDFORMATION_STACK_STATUS_CHANGE_EVENT_DETAIL_TYPE,
  DEFAULT_EVENT_QUEUE_NAME,
  DEPLOY_STATUS_EVENT_DETAIL_TYPE,
  EVENT_DATA_TABLE_INDEX_OBJS,
  EVENT_TABLE_NAME,
  SLACK_TOPIC_NAME,
  STACK_DATA_TABLE_INDEX_NAMES,
  STACK_PREFIX,
  STACK_TABLE_NAME,
} from './constants';
import { EVENT_BUS_NAME } from '@orcabus/platform-cdk-constructs/shared-config/event-bridge';
import {
  getDefaultApiGatewayConfiguration,
  HOSTED_ZONE_DOMAIN_PARAMETER_NAME,
} from '@orcabus/platform-cdk-constructs/api-gateway';
import { StatefulApplicationStackConfig, StatelessApplicationStackConfig } from './interfaces';

export const getStatefulStackProps = (): StatefulApplicationStackConfig => {
  return {
    // Stack Table stuff
    stackTableDbName: STACK_TABLE_NAME,
    stackTableIndexNames: STACK_DATA_TABLE_INDEX_NAMES,

    // Event table stuff
    eventTableDbName: EVENT_TABLE_NAME,
    eventTableIndexObjs: EVENT_DATA_TABLE_INDEX_OBJS,

    // SQS Stuff
    cloudFormationSqsQueueName: DEFAULT_EVENT_QUEUE_NAME,
    slackTopicName: SLACK_TOPIC_NAME,
  };
};

export const getStatelessStackProps = (stage: StageName): StatelessApplicationStackConfig => {
  return {
    // Stack Table stuff
    stackTableDbName: STACK_TABLE_NAME,
    stackTableIndexNames: STACK_DATA_TABLE_INDEX_NAMES,

    // Event table stuff
    eventTableDbName: EVENT_TABLE_NAME,
    eventTableIndexObjs: EVENT_DATA_TABLE_INDEX_OBJS,

    // Event Stuff
    externalEventBusName: EVENT_BUS_NAME,
    internalEventBusName: AWS_DEFAULT_EVENT_BUS,
    cloudFormationStateChangeEventDetailType: CLOUDFORMATION_STACK_STATUS_CHANGE_EVENT_DETAIL_TYPE,

    // Put Event Stuff
    eventSource: STACK_PREFIX,
    deployStatusStateChangeEventDetail: DEPLOY_STATUS_EVENT_DETAIL_TYPE,

    // SSM Stuff
    hostedZoneSsmParameterName: HOSTED_ZONE_DOMAIN_PARAMETER_NAME,

    // SQS Stuff
    cloudFormationStateChangeQueueName: DEFAULT_EVENT_QUEUE_NAME,
    slackTopicName: SLACK_TOPIC_NAME,

    // API Gateway stuff
    apiGatewayCognitoProps: {
      ...getDefaultApiGatewayConfiguration(stage),
      apiName: 'DeployStatusManager',
      customDomainNamePrefix: 'deploy-status',
    },
  };
};
