import * as schemas from 'aws-cdk-lib/aws-eventschemas';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import {
  EVENT_SCHEMAS_DIR,
  SCHEMA_REGISTRY_NAME,
  SSM_SCHEMA_ROOT,
  STACK_PREFIX,
} from '../constants';
import * as path from 'path';
import * as fs from 'fs';
import {
  schemaNamesList,
  BuildSchemaProps,
  schemaVersionListBySchemaNamesList,
} from './interfaces';
import { Construct } from 'constructs';
import { camelCaseToKebabCase } from '../utils';

export function buildSchema(scope: Construct, props: BuildSchemaProps): schemas.CfnSchema {
  // Import the schema file from the schemas directory
  const schemaPath = path.join(
    EVENT_SCHEMAS_DIR,
    camelCaseToKebabCase(props.schemaName),
    props.schemaVersion,
    'schema.json'
  );

  // Create a new schema in the Event Schemas service
  return new schemas.CfnSchema(scope, `${props.schemaName}--${props.schemaVersion}--schema`, {
    type: 'JSONSchemaDraft4',
    content: fs.readFileSync(schemaPath, 'utf-8'),
    registryName: SCHEMA_REGISTRY_NAME,
    schemaName: `${STACK_PREFIX}--${props.schemaName}--${props.schemaVersion}`,
  });
}

export function buildSchemas(scope: Construct) {
  // Add an ssm entry for the registry name
  new ssm.StringParameter(scope, `${SCHEMA_REGISTRY_NAME}-ssm`, {
    parameterName: path.join(SSM_SCHEMA_ROOT, 'registry'),
    stringValue: SCHEMA_REGISTRY_NAME,
  });

  // Iterate over the schemas directory and create a schema for each file
  for (const schemaName of schemaNamesList) {
    for (const schemaVersion of schemaVersionListBySchemaNamesList[schemaName]) {
      const schemaObj = buildSchema(scope, {
        schemaName: schemaName,
        schemaVersion: schemaVersion,
      });
      // Likely the one most commonly used
      new ssm.StringParameter(scope, `${schemaName}-ssm-${schemaVersion}`, {
        parameterName: path.join(SSM_SCHEMA_ROOT, camelCaseToKebabCase(schemaName), schemaVersion),
        stringValue: JSON.stringify({
          registryName: schemaObj.registryName,
          schemaName: schemaObj.attrSchemaName,
          schemaVersion: schemaObj.attrSchemaVersion,
        }),
      });
    }
  }
}
