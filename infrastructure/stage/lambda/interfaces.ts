import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { IQueue } from 'aws-cdk-lib/aws-sqs';
import { SfnName } from '../step-functions/interfaces';

export type LambdaName =
  // SQS Handling / Our Durable Function
  | 'handleDeployStatusSqs'
  // Process CFN Event Lambdas
  | 'addStackEvent'
  | 'getCommitIdFromStack'
  | 'getEventIdAndTimestamp'
  | 'getStackOrcabusId'
  | 'updateCallback';

/* Lambda names array */
/* Bit of double handling, BUT types are not parsed to JS */
export const lambdaNameList: Array<LambdaName> = [
  // SQS Handling / Our Durable Function
  'handleDeployStatusSqs',
  // Process CFN Event Lambdas
  'addStackEvent',
  'getCommitIdFromStack',
  'getEventIdAndTimestamp',
  'getStackOrcabusId',
  'updateCallback',
];

/* We also throw in our custom application interfaces here too */
export interface LambdaRequirementProps {
  needsOrcabusToolkitLayer?: boolean;
  needsSqsEventSource?: boolean;
  needsDurableExecutionPermissions?: boolean;
  needsSfnExecutablePermissions?: boolean;
  needsCFDescribePermissions?: boolean;
  needsCallbackPermissions?: boolean;
}

export type LambdaToRequirementsMapType = { [key in LambdaName]: LambdaRequirementProps };

export const lambdaToRequirementsMap: LambdaToRequirementsMapType = {
  // SQS Handling / Our Durable Function
  handleDeployStatusSqs: {
    needsSqsEventSource: true,
    needsDurableExecutionPermissions: true,
    needsSfnExecutablePermissions: true,
  },
  // Process CFN Event Lambdas
  addStackEvent: {
    needsOrcabusToolkitLayer: true,
  },
  getCommitIdFromStack: {
    needsCFDescribePermissions: true,
  },
  getEventIdAndTimestamp: {
    needsCFDescribePermissions: true,
  },
  getStackOrcabusId: {
    needsOrcabusToolkitLayer: true,
  },
  updateCallback: {
    needsCallbackPermissions: true,
  },
};

export interface BuildAllLambdasProps {
  cloudFormationStateChangeQueue: IQueue;
  processCfEventSfnName: SfnName;
}

export interface BuildLambdaProps extends BuildAllLambdasProps {
  lambdaName: LambdaName;
}

export interface LambdaObject {
  lambdaName: LambdaName;
  lambdaFunction: PythonFunction;
}
