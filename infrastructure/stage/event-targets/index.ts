/* Event Bridge Target Stuff */
import * as eventsTargets from 'aws-cdk-lib/aws-events-targets';
import * as events from 'aws-cdk-lib/aws-events';
import {
  AddSfnAsEventBridgeTargetProps,
  eventBridgeTargetsNameList,
  EventBridgeTargetsProps,
} from './interfaces';

function buildSfnEventBridgeTarget(props: AddSfnAsEventBridgeTargetProps): void {
  props.eventBridgeRuleObj.ruleObject.addTarget(
    new eventsTargets.SfnStateMachine(props.stateMachineObj.stateMachineObj, {
      input: events.RuleTargetInput.fromEventPath('$.detail'),
    })
  );
}

export function buildAllEventBridgeTargets(props: EventBridgeTargetsProps): void {
  /* Iterate over each event bridge rule and add the target */
  for (const eventBridgeTargetsName of eventBridgeTargetsNameList) {
    switch (eventBridgeTargetsName) {
      case 'cloudFormationStateChangeTargetToSqsQueue': {
        buildSfnEventBridgeTarget(<AddSfnAsEventBridgeTargetProps>{
          eventBridgeRuleObj: props.eventBridgeRuleObjects.find(
            (eventBridgeObject) => eventBridgeObject.ruleName === 'cloudFormationStateChangeRule'
          ),
          stateMachineObj: props.stepFunctionObjects.find(
            (sfnObject) => sfnObject.stateMachineName === 'addCfEventToSqsQueue'
          ),
        });
        break;
      }
    }
  }
}
