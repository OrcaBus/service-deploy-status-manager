import { StateMachine } from 'aws-cdk-lib/aws-stepfunctions';
import { LambdaName, LambdaObject } from '../lambda/interfaces';
import { IQueue } from 'aws-cdk-lib/aws-sqs';

export type SfnName = 'addCfEventToSqsQueue' | 'processCfEvent';

export const sfnNameList: Array<SfnName> = ['addCfEventToSqsQueue', 'processCfEvent'];

export interface BuildSfnsProps {
  /* Naming formation */
  lambdaFunctions: LambdaObject[];
  /* Sqs Queue */
  sqsQueue: IQueue;
}

export interface SfnProps extends BuildSfnsProps {
  /* Naming formation */
  stateMachineName: SfnName;
}

export interface SfnObject extends SfnProps {
  /* The state machine object */
  stateMachineObj: StateMachine;
}

export interface SfnPropsWithObject extends SfnProps {
  stateMachineObj: StateMachine;
}

export const stepFunctionToLambdaMap: { [key in SfnName]: Array<LambdaName> } = {
  addCfEventToSqsQueue: [],
  processCfEvent: [
    'addStackEvent',
    'getCommitIdFromStack',
    'getEventIdAndTimestamp',
    'getStackOrcabusId',
    'updateCallback',
  ],
};

export interface StepFunctionsRequirements {
  needsSqsSendMessagePermissions?: boolean;
}

export const stepFunctionsRequirementsMap: Record<SfnName, StepFunctionsRequirements> = {
  // Initialisation
  addCfEventToSqsQueue: {
    needsSqsSendMessagePermissions: true,
  },
  processCfEvent: {},
};
