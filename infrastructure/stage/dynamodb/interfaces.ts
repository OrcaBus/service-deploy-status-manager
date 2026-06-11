export interface GsiObject {
  indexName: string;
  partitionKey: string;
  sortKey?: string;
}

export interface BuildCloudFormationEventTableProps {
  /* The name of the table */
  tableName: string;

  /* The names of the indexes */
  indexObjs: GsiObject[];
}

export interface BuildStackTableProps {
  /* The name of the table */
  tableName: string;

  /* The names of the indexes */
  indexNames: string[];
}
