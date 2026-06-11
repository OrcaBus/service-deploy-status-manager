import { OrcaBusApiGatewayProps } from '@orcabus/platform-cdk-constructs/api-gateway';
import { SqsQueueName } from './sqs/interfaces';
import { GsiObject } from './dynamodb/interfaces';

export interface StatefulApplicationStackConfig {
  // Stack Table stuff
  stackTableDbName: string;
  stackTableIndexNames: string[];

  // Event table stuff
  eventTableDbName: string;
  eventTableIndexObjs: GsiObject[];

  // SQS Stuff
  cloudFormationSqsQueueName: SqsQueueName;
  slackTopicName: string;
}

export interface StatelessApplicationStackConfig {
  // Stack Table stuff
  stackTableDbName: string;
  stackTableIndexNames: string[];

  // Event table stuff
  eventTableDbName: string;
  eventTableIndexObjs: GsiObject[];

  // Event Stuff
  externalEventBusName: string;
  internalEventBusName: string;
  cloudFormationStateChangeEventDetailType: string;

  // Put Event Stuff
  eventSource: string;
  deployStatusStateChangeEventDetail: string;

  // SSM Stuff
  hostedZoneSsmParameterName: string;

  // SQS Stuff
  cloudFormationStateChangeQueueName: string;
  slackTopicName: string;

  // API Gateway stuff
  apiGatewayCognitoProps: OrcaBusApiGatewayProps;
}
