import { PythonUvFunction } from '@orcabus/platform-cdk-constructs/lambda';
import path from 'path';
import { API_VERSION, DEPLOY_STATUS_SUBDOMAIN_NAME, INTERFACE_DIR } from '../constants';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { NagSuppressions } from 'cdk-nag';
import {
  OrcaBusApiGateway,
  OrcaBusApiGatewayProps,
} from '@orcabus/platform-cdk-constructs/api-gateway';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import {
  HttpMethod,
  HttpNoneAuthorizer,
  HttpRoute,
  HttpRouteKey,
} from 'aws-cdk-lib/aws-apigatewayv2';
import { Construct } from 'constructs';
import { BuildApiIntegrationProps, BuildHttpRoutesProps, LambdaApiProps } from './interfaces';

export function buildApiInterfaceLambda(scope: Construct, props: LambdaApiProps) {
  // Create the lambda function
  const lambdaFunction = new PythonUvFunction(scope, props.lambdaName, {
    entry: path.join(INTERFACE_DIR),
    runtime: lambda.Runtime.PYTHON_3_14,
    architecture: lambda.Architecture.ARM_64,
    index: 'handler.py',
    handler: 'handler',
    memorySize: 2048,
    includeFastApiLayer: true,
    includeOrcabusApiToolsLayer: true,
    timeout: Duration.seconds(60),
  });

  // Add the table in as an environment variable
  // And allow the lambda to write + read from the table
  lambdaFunction.addEnvironment('DYNAMODB_EVENT_TABLE_NAME', props.eventDataTable.tableName);
  lambdaFunction.addEnvironment('DYNAMODB_STACK_TABLE_NAME', props.stackDataTable.tableName);
  lambdaFunction.addEnvironment(
    'DYNAMODB_HOST',
    `https://dynamodb.${cdk.Aws.REGION}.amazonaws.com`
  );
  props.eventDataTable.grantReadWriteData(lambdaFunction);
  props.stackDataTable.grantReadWriteData(lambdaFunction);

  // // Add index tables
  // const stackTableIndexArns: string[] = props.stackDataTableIndexNames.map((index_name) => {
  //   return `arn:aws:dynamodb:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:table/${props.stackDataTable.tableName}/index/${index_name}-index`;
  // });
  //
  // // Add index arns to role policy
  // lambdaFunction.addToRolePolicy(
  //   new iam.PolicyStatement({
  //     actions: ['dynamodb:Query'],
  //     resources: stackTableIndexArns,
  //   })
  // );

  // Add index tables
  const eventTableIndexArns: string[] = props.eventTableIndexObjs.map((index_obj) => {
    return `arn:aws:dynamodb:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:table/${props.eventDataTable.tableName}/index/${index_obj.indexName}-index`;
  });

  // Add index arns to role policy
  lambdaFunction.addToRolePolicy(
    new iam.PolicyStatement({
      actions: ['dynamodb:Query'],
      resources: eventTableIndexArns,
    })
  );

  // Add the event bus in as an environment variable
  // And allow the lambda to put events to the event bus
  lambdaFunction.addEnvironment('EVENT_BUS_NAME', props.eventBus.eventBusName);
  props.eventBus.grantPutEventsTo(lambdaFunction);

  // Few extra env vars
  lambdaFunction.addEnvironment('EVENT_SOURCE', props.eventSource);
  lambdaFunction.addEnvironment(
    'EVENT_DETAIL_TYPE_ANALYSIS_STATE_CHANGE',
    props.deployStatusStateChangeEventDetail
  );

  lambdaFunction.addEnvironment(
    'DEPLOY_STATUS_BASE_URL',
    `https://${DEPLOY_STATUS_SUBDOMAIN_NAME}.${props.hostedZoneSsmParameter.stringValue}`
  );

  // // Allow the cloudformation:DescribeStacks on any stack in the account
  // lambdaFunction.addToRolePolicy(
  //   new iam.PolicyStatement({
  //     actions: ['cloudformation:DescribeStacks'],
  //     resources: [`arn:aws:cloudformation:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stack/*`]
  //   })
  // );
  //
  // // Add an IAM-5 nag suppression
  // NagSuppressions.addResourceSuppressions(
  //   lambdaFunction,
  //   [
  //     {
  //       id: 'AwsSolutions-IAM5',
  //       reason: 'Need access to describe all cloud formation stacks.',
  //     },
  //   ],
  //   true
  // );

  return lambdaFunction;
}

export function buildApiGateway(
  scope: Construct,
  props: OrcaBusApiGatewayProps
): OrcaBusApiGateway {
  return new OrcaBusApiGateway(scope, 'apiGateway', props);
}

export function buildApiIntegration(props: BuildApiIntegrationProps): HttpLambdaIntegration {
  return new HttpLambdaIntegration('ApiIntegration', props.lambdaFunction);
}

// Add the http routes to the API Gateway
export function addHttpRoutes(scope: Construct, props: BuildHttpRoutesProps) {
  // Routes for API schemas
  const schemaRoute = new HttpRoute(scope, 'GetSchemaHttpRoute', {
    httpApi: props.apiGateway.httpApi,
    integration: props.apiIntegration,
    authorizer: new HttpNoneAuthorizer(), // No auth needed for schema
    routeKey: HttpRouteKey.with(`/schema/{PROXY+}`, HttpMethod.GET),
  });
  NagSuppressions.addResourceSuppressions(
    schemaRoute,
    [
      {
        id: 'AwsSolutions-APIG4',
        reason: 'This is a public API endpoint for schema access, no auth needed.',
      },
    ],
    true
  );
  new HttpRoute(scope, 'GetHttpRoute', {
    httpApi: props.apiGateway.httpApi,
    integration: props.apiIntegration,
    routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.GET),
  });
  new HttpRoute(scope, 'PostHttpRoute', {
    httpApi: props.apiGateway.httpApi,
    integration: props.apiIntegration,
    authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
    routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.POST),
  });
  new HttpRoute(scope, 'PatchHttpRoute', {
    httpApi: props.apiGateway.httpApi,
    integration: props.apiIntegration,
    authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
    routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.PATCH),
  });
  new HttpRoute(scope, 'DeleteHttpRoute', {
    httpApi: props.apiGateway.httpApi,
    integration: props.apiIntegration,
    authorizer: props.apiGateway.authStackHttpLambdaAuthorizer,
    routeKey: HttpRouteKey.with(`/api/${API_VERSION}/{PROXY+}`, HttpMethod.DELETE),
  });
}
