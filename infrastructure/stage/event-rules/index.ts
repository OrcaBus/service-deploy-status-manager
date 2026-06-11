import {
  BuildEventBridgeRulesProps,
  eventBridgeRuleNameList,
  EventBridgeRuleObject,
  EventBridgeRuleProps,
  BuildCloudFormationStateChangeRuleProps,
  CloudFormationStateChangeEventPatternProps,
} from './interfaces';
import { Rule } from 'aws-cdk-lib/aws-events';
import { Construct } from 'constructs';
import * as events from 'aws-cdk-lib/aws-events';

/** Event bridge rules stuff */
function buildCloudFormationStateChangeEventPattern(
  props: CloudFormationStateChangeEventPatternProps
) {
  return {
    detailType: [props.cloudFormationStateChangeEventDetailType],
  };
}

function buildEventRule(scope: Construct, props: EventBridgeRuleProps): Rule {
  return new events.Rule(scope, props.ruleName, {
    ruleName: props.ruleName,
    eventPattern: props.eventPattern,
    eventBus: props.eventBus,
  });
}

function buildCloudFormationStateChangeRule(
  scope: Construct,
  props: BuildCloudFormationStateChangeRuleProps
): Rule {
  return buildEventRule(scope, {
    ruleName: props.ruleName,
    eventPattern: buildCloudFormationStateChangeEventPattern(props),
    eventBus: props.eventBus,
  });
}

export function buildEventBridgeRules(
  scope: Construct,
  props: BuildEventBridgeRulesProps
): EventBridgeRuleObject[] {
  const eventBridgeObjects: EventBridgeRuleObject[] = [];
  for (const eventBridgeRuleName of eventBridgeRuleNameList) {
    switch (eventBridgeRuleName) {
      case 'cloudFormationStateChangeRule': {
        eventBridgeObjects.push({
          ruleName: eventBridgeRuleName,
          ruleObject: buildCloudFormationStateChangeRule(scope, {
            ruleName: eventBridgeRuleName,
            eventBus: props.eventBus,
            cloudFormationStateChangeEventDetailType:
              props.cloudFormationStateChangeEventDetailType,
          }),
          eventBus: props.eventBus,
        });
        break;
      }
    }
  }
  return eventBridgeObjects;
}
