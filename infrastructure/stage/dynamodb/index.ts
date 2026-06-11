import { GlobalSecondaryIndexPropsV2 } from 'aws-cdk-lib/aws-dynamodb/lib/table-v2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { AttributeType } from 'aws-cdk-lib/aws-dynamodb';
import { TABLE_REMOVAL_POLICY } from '../constants';
import { BuildCloudFormationEventTableProps, BuildStackTableProps } from './interfaces';
import { Construct } from 'constructs';

export function buildStackTableDb(scope: Construct, props: BuildStackTableProps) {
  /*
        First generate the global secondary index for the 'name' field
        Hopefully this construct will be useful for other projects as well
        */
  const globalSecondaryIndexes: GlobalSecondaryIndexPropsV2[] = [];
  for (const indexName of props.indexNames) {
    globalSecondaryIndexes.push({
      indexName: `${indexName}-index`,
      partitionKey: {
        name: indexName,
        type: AttributeType.STRING,
      },
      sortKey: {
        name: 'orcabus_id',
        type: AttributeType.STRING,
      },
    });
  }

  new dynamodb.TableV2(scope, props.tableName, {
    partitionKey: {
      name: 'orcabus_id',
      type: AttributeType.STRING,
    },
    tableName: props.tableName,
    removalPolicy: TABLE_REMOVAL_POLICY,
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
    globalSecondaryIndexes: globalSecondaryIndexes,
  });
}

export function buildEventTableDb(scope: Construct, props: BuildCloudFormationEventTableProps) {
  /*
        First generate the global secondary index for the 'name' field
        Hopefully this construct will be useful for other projects as well
        */
  const globalSecondaryIndexes: GlobalSecondaryIndexPropsV2[] = [];
  for (const indexObj of props.indexObjs) {
    globalSecondaryIndexes.push({
      indexName: `${indexObj.indexName}-index`,
      partitionKey: {
        name: indexObj.partitionKey,
        type: AttributeType.STRING,
      },
      ...(indexObj.sortKey
        ? {
            sortKey: {
              name: indexObj.sortKey,
              type: AttributeType.STRING,
            },
          }
        : {}),
    });
  }

  new dynamodb.TableV2(scope, props.tableName, {
    partitionKey: {
      name: 'orcabus_id',
      type: AttributeType.STRING,
    },
    sortKey: {
      name: 'stack_name',
      type: AttributeType.STRING,
    },
    tableName: props.tableName,
    removalPolicy: TABLE_REMOVAL_POLICY,
    pointInTimeRecoverySpecification: {
      pointInTimeRecoveryEnabled: true,
    },
    globalSecondaryIndexes: globalSecondaryIndexes,
  });
}
