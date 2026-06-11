// Standard cdk imports
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

// Application imports
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as events from 'aws-cdk-lib/aws-events';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

// Local imports
import { StatelessApplicationStackConfig } from './interfaces';
import { NagSuppressions } from 'cdk-nag';
import { StageName } from '@orcabus/platform-cdk-constructs/shared-config/accounts';
import { buildAllLambdas } from './lambda';
import { buildAllStepFunctions } from './step-functions';
import { buildEventBridgeRules } from './event-rules';
import { buildAllEventBridgeTargets } from './event-targets';
import {
  addHttpRoutes,
  buildApiGateway,
  buildApiIntegration,
  buildApiInterfaceLambda,
} from './api';
import { GitStack } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';

export type StatelessApplicationStackProps = StatelessApplicationStackConfig & cdk.StackProps;

// Stateless Application Stack
export class StatelessApplicationStack extends GitStack {
  public readonly stageName: StageName;
  constructor(scope: Construct, id: string, props: StatelessApplicationStackProps) {
    super(scope, id, props);

    // Get dynamodb table (built in the stateful stack)
    const stackDataTable = dynamodb.TableV2.fromTableName(
      this,
      props.stackTableDbName,
      props.stackTableDbName
    );
    const eventDataTable = dynamodb.TableV2.fromTableName(
      this,
      props.eventTableDbName,
      props.eventTableDbName
    );

    // Get the event bus objects
    const externalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.externalEventBusName,
      props.externalEventBusName
    );
    const internalEventBusObject = events.EventBus.fromEventBusName(
      this,
      props.internalEventBusName,
      props.internalEventBusName
    );

    // SSM parameters
    const hostedZoneSsmParameterObj = ssm.StringParameter.fromStringParameterName(
      this,
      props.hostedZoneSsmParameterName,
      props.hostedZoneSsmParameterName
    );

    // Get the SQS Queue from props
    const cloudFormationStateChangeQueue: IQueue = sqs.Queue.fromQueueArn(
      this,
      props.cloudFormationStateChangeQueueName,
      `arn:aws:sqs:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:${props.cloudFormationStateChangeQueueName}`
    );

    // Build the lambdas
    const lambdaObjects = buildAllLambdas(this, {
      cloudFormationStateChangeQueue: cloudFormationStateChangeQueue,
      processCfEventSfnName: 'processCfEvent',
    });

    // Build the step functions
    const stepFunctionObjects = buildAllStepFunctions(this, {
      sqsQueue: cloudFormationStateChangeQueue,
      lambdaFunctions: lambdaObjects,
    });

    // Build event bridge rules
    const eventBridgeRuleObjects = buildEventBridgeRules(this, {
      /* Event buses */
      eventBus: internalEventBusObject,
      /* Detail Type */
      cloudFormationStateChangeEventDetailType: props.cloudFormationStateChangeEventDetailType,
    });

    // Add the event-bridge rules
    buildAllEventBridgeTargets({
      eventBridgeRuleObjects: eventBridgeRuleObjects,
      stepFunctionObjects: stepFunctionObjects,
    });

    // Build the API interface lambda
    const lambdaApi = buildApiInterfaceLambda(this, {
      /* The lambda name */
      lambdaName: 'deployStatusApi',

      /* Table to use */
      eventDataTable: eventDataTable,
      eventTableIndexObjs: props.eventTableIndexObjs,

      stackDataTable: stackDataTable,
      stackDataTableIndexNames: props.stackTableIndexNames,

      /* Event Bus */
      eventBus: externalEventBusObject,
      eventSource: props.eventSource,
      deployStatusStateChangeEventDetail: props.deployStatusStateChangeEventDetail,

      /* SSM Parameters */
      hostedZoneSsmParameter: hostedZoneSsmParameterObj,
    });

    // Build the API Gateway
    const apiGateway = buildApiGateway(this, props.apiGatewayCognitoProps);
    const apiIntegration = buildApiIntegration({
      lambdaFunction: lambdaApi,
    });
    addHttpRoutes(this, {
      apiGateway: apiGateway,
      apiIntegration: apiIntegration,
    });

    // Add in stack suppressions
    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'We need to add this for the lambdas to work',
      },
    ]);
  }
}
