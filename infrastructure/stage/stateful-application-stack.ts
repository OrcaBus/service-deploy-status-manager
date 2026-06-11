/*
Stateful Application Stack

This involves a few things,

1. The database to serve the API / Jobs
    Will need a global index on the 'name' field

2. The ICAv2 Event Pipe
3. The Internal Event Bus for the Event Pipe to publish to
*/

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { StatefulApplicationStackConfig } from './interfaces';
import { DEFAULT_SQS_LAMBDA_TIMEOUT } from './constants';
import { createMonitoredQueue, getTopicArnFromTopicName } from './sqs';
import { buildEventTableDb, buildStackTableDb } from './dynamodb';
import { buildSchemas } from './event-schemas';
import { Topic } from 'aws-cdk-lib/aws-sns';
import { Duration } from 'aws-cdk-lib';
import { GitStack } from '@orcabus/platform-cdk-constructs/deployment-stack-pipeline';

export type StatefulApplicationStackProps = StatefulApplicationStackConfig & cdk.StackProps;

// Stateful Application Stack
export class StatefulApplicationStack extends GitStack {
  constructor(scope: Construct, id: string, props: StatefulApplicationStackProps) {
    super(scope, id, props);
    // Slack topic ARN
    // However, our use case, as we don't add any additional subscriptions, does not require topic modification, so we can pass on an "ITopic" as "Topic".
    const slackTopic: Topic = Topic.fromTopicArn(
      this,
      'SlackTopic',
      getTopicArnFromTopicName(props.slackTopicName)
    ) as Topic;

    // Build Dynamodb table
    buildStackTableDb(this, {
      tableName: props.stackTableDbName,
      indexNames: props.stackTableIndexNames,
    });
    buildEventTableDb(this, {
      tableName: props.eventTableDbName,
      indexObjs: props.eventTableIndexObjs,
    });

    // SQS
    createMonitoredQueue(this, {
      dlqMessageThreshold: 1,
      queueName: props.cloudFormationSqsQueueName,
      queueVizTimeout: DEFAULT_SQS_LAMBDA_TIMEOUT,
      slackTopic: slackTopic,
      receiveMessageWaitTime: Duration.seconds(20),
    });

    // Create schemas
    buildSchemas(this);
  }
}
