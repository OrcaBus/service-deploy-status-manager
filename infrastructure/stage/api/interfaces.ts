import { ITableV2 } from 'aws-cdk-lib/aws-dynamodb';
import { IEventBus } from 'aws-cdk-lib/aws-events';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { OrcaBusApiGateway } from '@orcabus/platform-cdk-constructs/api-gateway';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { IStringParameter } from 'aws-cdk-lib/aws-ssm';
import { GsiObject } from '../dynamodb/interfaces';

export interface LambdaApiProps {
  /* The lambda name */
  lambdaName: string;

  /* Table to use */
  eventDataTable: ITableV2;
  eventTableIndexObjs: GsiObject[];

  stackDataTable: ITableV2;
  stackDataTableIndexNames: string[];

  /* Event Bus */
  eventBus: IEventBus;
  eventSource: string;
  deployStatusStateChangeEventDetail: string;

  /* SSM Parameters */
  hostedZoneSsmParameter: IStringParameter;
}

/** API Interfaces */
/** API Gateway interfaces **/
export interface BuildApiIntegrationProps {
  lambdaFunction: PythonFunction;
}

export interface BuildHttpRoutesProps {
  apiGateway: OrcaBusApiGateway;
  apiIntegration: HttpLambdaIntegration;
}
