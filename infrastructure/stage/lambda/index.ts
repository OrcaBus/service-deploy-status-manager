/* Lambda stuff */
import {
  BuildAllLambdasProps,
  BuildLambdaProps,
  lambdaNameList,
  LambdaObject,
  lambdaToRequirementsMap,
} from './interfaces';
import { DEFAULT_MAX_SQS_LAMBDA_CONCURRENCY, LAMBDA_DIR, STACK_PREFIX } from '../constants';
import { PythonUvFunction } from '@orcabus/platform-cdk-constructs/lambda';
import { Construct } from 'constructs';
import { camelCaseToSnakeCase } from '../utils';
import * as path from 'path';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { NagSuppressions } from 'cdk-nag';
import { Duration } from 'aws-cdk-lib';
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cdk from 'aws-cdk-lib';

export function buildAllLambdas(scope: Construct, props: BuildAllLambdasProps): LambdaObject[] {
  // Iterate over lambdaLayerToMapping and create the lambda functions
  const lambdaObjects: LambdaObject[] = [];
  for (const lambdaName of lambdaNameList) {
    lambdaObjects.push(
      buildLambda(scope, {
        lambdaName: lambdaName,
        ...props,
      })
    );
  }

  return lambdaObjects;
}

/** Lambda stuff */
function buildLambda(scope: Construct, props: BuildLambdaProps): LambdaObject {
  const lambdaNameToSnakeCase = camelCaseToSnakeCase(props.lambdaName);
  const lambdaRequirements = lambdaToRequirementsMap[props.lambdaName];

  // Create the lambda function
  const lambdaFunction = new PythonUvFunction(scope, props.lambdaName, {
    entry: path.join(LAMBDA_DIR, lambdaNameToSnakeCase + '_py'),
    runtime: lambda.Runtime.PYTHON_3_14,
    architecture: lambda.Architecture.ARM_64,
    index: lambdaNameToSnakeCase + '.py',
    handler: 'handler',
    // And if we have a lot of data to process, we need more memory
    includeOrcabusApiToolsLayer: lambdaRequirements.needsOrcabusTookitLayer,
    // Dynamodb can take a second to spin up
    timeout: Duration.seconds(10),
    durableConfig: lambdaRequirements.needsDurableExecutionPermissions
      ? {
          executionTimeout: Duration.minutes(15),
          retentionPeriod: Duration.days(1),
        }
      : undefined,
  });

  // If the lambda has an SQS event source, we need to add this in
  // Generate Event Request uses the launch ICA Source Event Queue
  if (lambdaRequirements.needsSqsEventSource) {
    if (props.lambdaName == 'handleDeployStatusSqs') {
      // Find the SQS queue from the props
      lambdaFunction.latestVersion.addEventSource(
        new SqsEventSource(props.cloudFormationStateChangeQueue, {
          maxConcurrency: DEFAULT_MAX_SQS_LAMBDA_CONCURRENCY,
          // Allow only one message per batch to be processed
          batchSize: 1,
        })
      );
    }
  }

  if (lambdaRequirements.needsCFDescribePermissions) {
    // Lambda needs permissions to access a cloud formation stack
    lambdaFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudformation:DescribeStacks', 'cloudformation:DescribeStackEvents'],
        resources: ['*'],
      })
    );

    // Add resource suppressions
    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Adding resources * to our describe stacks policy as we need to describe any stack that triggers a change',
        },
      ],
      true
    );
  }

  if (lambdaRequirements.needsSfnExecutablePermissions) {
    if (props.lambdaName == 'handleDeployStatusSqs') {
      // Add the step function
      // Update the environment variable for the step function name
      // When we generate the state machine we will give the lambda permission to start the execution
      lambdaFunction.addEnvironment(
        'HANDLE_CFN_STATE_CHANGE_SFN_ARN',
        `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:${STACK_PREFIX}--${props.processCfEventSfnName}`
      );
    }
  }

  if (lambdaRequirements.needsCallbackPermissions) {
    // Grant write permissions to allow the lambda to unlock durable executions
    // We don't know the exact resource ARNs here since they are created dynamically
    lambdaFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['lambda:SendDurableExecutionCallbackSuccess'],
        resources: [
          `arn:aws:lambda:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:function:*:*/durable-execution/*/*`,
        ],
      })
    );

    // Add resource suppressions
    NagSuppressions.addResourceSuppressions(
      lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Send DurableExecutionCallback success permissions to dynamic resources.',
          appliesTo: [
            'Resource::arn:aws:lambda:<AWS::Region>:<AWS::AccountId>:function:*:*/durable-execution/*/*',
          ],
        },
      ],
      true
    );
  }

  /* Return the function */
  return {
    lambdaName: props.lambdaName,
    lambdaFunction: lambdaFunction,
  };
}
