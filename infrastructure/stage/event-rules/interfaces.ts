import { EventPattern, IEventBus, Rule } from 'aws-cdk-lib/aws-events';

export type EventBridgeRuleName =
  // External rule - for requests to run analyses
  'cloudFormationStateChangeRule';

export const eventBridgeRuleNameList: Array<EventBridgeRuleName> = [
  'cloudFormationStateChangeRule',
];

export interface CloudFormationStateChangeEventPatternProps {
  cloudFormationStateChangeEventDetailType: string;
}

export interface EventBridgeRuleProps {
  ruleName: EventBridgeRuleName;
  eventBus: IEventBus;
  eventPattern: EventPattern;
}

export interface EventBridgeRuleObject {
  ruleName: EventBridgeRuleName;
  ruleObject: Rule;
  eventBus: IEventBus;
}

export type BuildCloudFormationStateChangeRuleProps = Omit<
  CloudFormationStateChangeEventPatternProps & EventBridgeRuleProps,
  'eventPattern'
>;

export interface BuildEventBridgeRulesProps {
  /* Event Buses */
  eventBus: IEventBus;

  /* Event Patterns - Detail Type */
  cloudFormationStateChangeEventDetailType: string;
}
