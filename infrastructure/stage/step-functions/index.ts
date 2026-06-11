/*
Build the step functions
 */

// Imports
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import { Construct } from 'constructs';
import * as path from 'path';

// Local interfaces
import {
  BuildSfnsProps,
  sfnNameList,
  SfnObject,
  SfnProps,
  SfnPropsWithObject,
  stepFunctionsRequirementsMap,
  stepFunctionToLambdaMap,
} from './interfaces';
import { camelCaseToSnakeCase } from '../utils';
import { NagSuppressions } from 'cdk-nag';
import { STACK_PREFIX, STEP_FUNCTIONS_DIR } from '../constants';
import { LambdaObject } from '../lambda/interfaces';

/** Step Function stuff */
function createStateMachineDefinitionSubstitutions(props: SfnProps): {
  [key: string]: string;
} {
  const definitionSubstitutions: { [key: string]: string } = {};

  const sfnRequirements = stepFunctionsRequirementsMap[props.stateMachineName];
  const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
  const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
    lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
  );

  /* Substitute lambdas in the state machine definition */
  for (const lambdaObject of lambdaFunctions) {
    const sfnSubstitutionKey = `__${camelCaseToSnakeCase(lambdaObject.lambdaName)}_lambda_function_arn__`;
    definitionSubstitutions[sfnSubstitutionKey] =
      lambdaObject.lambdaFunction.latestVersion.functionArn;
  }

  /* Sfn Requirements */
  if (sfnRequirements.needsSqsSendMessagePermissions) {
    definitionSubstitutions['__sqs_queue_url__'] = props.sqsQueue.queueUrl;
  }

  return definitionSubstitutions;
}

function wireUpStateMachinePermissions(scope: Construct, props: SfnPropsWithObject): void {
  /* Wire up lambda permissions */
  const sfnRequirements = stepFunctionsRequirementsMap[props.stateMachineName];

  const lambdaFunctionNamesInSfn = stepFunctionToLambdaMap[props.stateMachineName];
  const lambdaFunctions = props.lambdaFunctions.filter((lambdaObject) =>
    lambdaFunctionNamesInSfn.includes(lambdaObject.lambdaName)
  );

  /* Allow the state machine to invoke the lambda function */
  for (const lambdaObject of lambdaFunctions) {
    lambdaObject.lambdaFunction.grantInvoke(props.stateMachineObj);
  }
  // Will need cdk nag suppressions for this
  // Because we are using a wildcard for an IAM Resource policy
  NagSuppressions.addResourceSuppressions(
    props.stateMachineObj,
    [
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Need ability to run any version of the lambda',
      },
    ],
    true
  );

  if (sfnRequirements.needsSqsSendMessagePermissions) {
    // Ability to send messages to a queue
    props.sqsQueue.grantSendMessages(props.stateMachineObj);
  }

  // From lambda, provide lambda object permission to run state machine
  if (props.stateMachineName === 'processCfEvent') {
    props.stateMachineObj.grantStartExecution(
      // Get the lambda function with the name 'handleDeployStatusSqs'
      (<LambdaObject>(
        props.lambdaFunctions.find(
          (lambdaObject) => lambdaObject.lambdaName === 'handleDeployStatusSqs'
        )
      )).lambdaFunction
    );
    // Will need cdk nag suppressions for this
    // Because we are using a wildcard for an IAM Resource policy
    NagSuppressions.addResourceSuppressions(
      props.stateMachineObj,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Grant execution to any version of the lambda',
        },
      ],
      true
    );
  }
}

function buildStepFunction(scope: Construct, props: SfnProps): SfnObject {
  const sfnNameToSnakeCase = camelCaseToSnakeCase(props.stateMachineName);

  /* Create the state machine definition substitutions */
  const stateMachine = new sfn.StateMachine(scope, props.stateMachineName, {
    stateMachineName: `${STACK_PREFIX}--${props.stateMachineName}`,
    definitionBody: sfn.DefinitionBody.fromFile(
      path.join(STEP_FUNCTIONS_DIR, sfnNameToSnakeCase + `_sfn_template.asl.json`)
    ),
    definitionSubstitutions: createStateMachineDefinitionSubstitutions(props),
  });

  /* Grant the state machine permissions */
  wireUpStateMachinePermissions(scope, {
    stateMachineObj: stateMachine,
    ...props,
  });

  /* Nag Suppressions */
  /* AwsSolutions-SF1 - We don't need ALL events to be logged */
  /* AwsSolutions-SF2 - We also don't need X-Ray tracing */
  NagSuppressions.addResourceSuppressions(
    stateMachine,
    [
      {
        id: 'AwsSolutions-SF1',
        reason: 'We do not need all events to be logged',
      },
      {
        id: 'AwsSolutions-SF2',
        reason: 'We do not need X-Ray tracing',
      },
    ],
    true
  );

  /* Return as a state machine object property */
  return {
    ...props,
    stateMachineObj: stateMachine,
  };
}

export function buildAllStepFunctions(scope: Construct, props: BuildSfnsProps): SfnObject[] {
  // Initialize the step function objects
  const sfnObjects = [] as SfnObject[];

  // Iterate over lambdaLayerToMapping and create the lambda functions
  for (const sfnName of sfnNameList) {
    sfnObjects.push(
      buildStepFunction(scope, {
        stateMachineName: sfnName,
        ...props,
      })
    );
  }

  return sfnObjects;
}
