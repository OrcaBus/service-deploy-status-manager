export type SchemaNames = 'stackStateChange';

export const schemaNamesList: SchemaNames[] = ['stackStateChange'];
export const schemaVersionListBySchemaNamesList: Record<SchemaNames, string[]> = {
  stackStateChange: ['2026.06.04'],
};

export interface BuildSchemaProps {
  schemaName: SchemaNames;
  schemaVersion: string;
}
