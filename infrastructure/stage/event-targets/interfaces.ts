import { EventBridgeRuleObject } from '../event-rules/interfaces';
import { SfnObject } from '../step-functions/interfaces';

export type EventBridgeTargetsNameList =
  // Cloud Formation State Change Target To Sqs Queue
  'cloudFormationStateChangeTargetToSqsQueue';

export const eventBridgeTargetsNameList: Array<EventBridgeTargetsNameList> = [
  // Cloud Formation State Change Target To Sqs Queue
  'cloudFormationStateChangeTargetToSqsQueue',
];

export interface EventBridgeTargetsProps {
  eventBridgeRuleObjects: EventBridgeRuleObject[];
  stepFunctionObjects: SfnObject[];
}

export interface AddSfnAsEventBridgeTargetProps {
  stateMachineObj: SfnObject;
  eventBridgeRuleObj: EventBridgeRuleObject;
}
