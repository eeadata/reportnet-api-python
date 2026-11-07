# Generated from spec/api-docs.json by scripts/regen_models.sh — do not edit by hand.

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, Base64Str, BaseModel, Field


class CheckLockVO(BaseModel):
    importInProgress: bool | None = None
    message: str | None = None


class CreateSnapshotVO(BaseModel):
    automatic: bool | None = None
    description: str | None = None
    released: bool | None = None


class DatasetRunningStatus(StrEnum):
    IN_QUEUE = "IN_QUEUE"
    ERROR_IN_VALIDATION = "ERROR_IN_VALIDATION"
    ERROR_IN_IMPORT = "ERROR_IN_IMPORT"
    IMPORTING = "IMPORTING"
    IMPORTED = "IMPORTED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    RESTORING_SNAPSHOT = "RESTORING_SNAPSHOT"


class DatasetTypeEnum(StrEnum):
    REPORTING = "REPORTING"
    DESIGN = "DESIGN"
    COLLECTION = "COLLECTION"
    TEST = "TEST"
    EUDATASET = "EUDATASET"
    REFERENCE = "REFERENCE"


class Status(StrEnum):
    FINAL_FEEDBACK = "FINAL_FEEDBACK"
    TECHNICALLY_ACCEPTED = "TECHNICALLY_ACCEPTED"
    PENDING = "PENDING"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"
    RELEASED = "RELEASED"
    MULTIPLE = "MULTIPLE"


class DataSetMetabaseVO(BaseModel):
    creationDate: AwareDatetime | None = None
    dataProviderId: int | None = None
    dataSetName: str | None = None
    dataflowId: int | None = None
    datasetRunningStatus: DatasetRunningStatus | None = None
    datasetSchema: str | None = None
    datasetTypeEnum: DatasetTypeEnum | None = None
    id: int | None = None
    status: Status | None = None


class LevelError(StrEnum):
    CORRECT = "CORRECT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    INFO = "INFO"
    BLOCKER = "BLOCKER"


class DatasetEditingStatusVO(BaseModel):
    datasetId: int | None = None
    editor: str | None = None
    isEditing: bool | None = None
    isLockedForUser: bool | None = None


class DatasetTableVO(BaseModel):
    datasetId: int | None = None
    datasetSchemaId: str | None = None
    id: int | None = None
    isIcebergTableCreated: bool | None = None
    tableName: str | None = None
    tableSchemaId: str | None = None


class ETLFieldVO(BaseModel):
    fieldName: str | None = None
    value: str | None = None


class ETLRecordVO(BaseModel):
    countryCode: str | None = None
    fields: list[ETLFieldVO] | None = None


class ETLTableVO(BaseModel):
    records: list[ETLRecordVO] | None = None
    tableName: str | None = None


class EUDatasetVO(BaseModel):
    creationDate: AwareDatetime | None = None
    dataSetName: str | None = None
    datasetSchema: str | None = None
    id: int | None = None
    idDataflow: int | None = None
    status: str | None = None


class LevelErrorEnum(StrEnum):
    CORRECT = "CORRECT"
    WARNING = "WARNING"
    ERROR = "ERROR"
    INFO = "INFO"
    BLOCKER = "BLOCKER"


class ExportFilterVO(BaseModel):
    fieldValue: str | None = None
    idRules: str | None = None
    levelError: list[LevelErrorEnum] | None = None
    qcCodes: str | None = None


class Type(StrEnum):
    TEXT = "TEXT"
    TEXTAREA = "TEXTAREA"
    LONG_TEXT = "LONG_TEXT"
    NUMBER_INTEGER = "NUMBER_INTEGER"
    NUMBER_DECIMAL = "NUMBER_DECIMAL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    POINT = "POINT"
    LINESTRING = "LINESTRING"
    POLYGON = "POLYGON"
    MULTIPOINT = "MULTIPOINT"
    MULTILINESTRING = "MULTILINESTRING"
    MULTIPOLYGON = "MULTIPOLYGON"
    GEOMETRYCOLLECTION = "GEOMETRYCOLLECTION"
    CODELIST = "CODELIST"
    MULTISELECT_CODELIST = "MULTISELECT_CODELIST"
    LINK = "LINK"
    EXTERNAL_LINK = "EXTERNAL_LINK"
    URL = "URL"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    ATTACHMENT = "ATTACHMENT"


class File(BaseModel):
    absolute: bool | None = None
    absoluteFile: File | None = None
    absolutePath: str | None = None
    canonicalFile: File | None = None
    canonicalPath: str | None = None
    directory: bool | None = None
    file: bool | None = None
    freeSpace: int | None = None
    hidden: bool | None = None
    name: str | None = None
    parent: str | None = None
    parentFile: File | None = None
    path: str | None = None
    totalSpace: int | None = None
    usableSpace: int | None = None


class ImportStatisticsVO(BaseModel):
    fileExtension: str | None = None
    lastImportDate: AwareDatetime | None = None
    numberOfRecordsImported: int | None = None


class ImportedFilesDirectoriesVO(BaseModel):
    creationDate: str | None = None
    creationDateTimestamp: int | None = None
    fileName: str | None = None
    fileSize: str | None = None
    lastModifiedTime: int | None = None


class InputStream(BaseModel):
    pass


class JobPresignedUrlInfo(BaseModel):
    filePathInS3: str | None = None
    jobId: int | None = None
    presignedUrl: str | None = None


class LockType(StrEnum):
    METHOD = "METHOD"
    ENTITY = "ENTITY"


class OrderVO(BaseModel):
    id: str | None = None
    position: int | None = None


class ReferencedFieldSchemaVO(BaseModel):
    dataflowId: int | None = None
    fieldSchemaName: str | None = None
    idDatasetSchema: str | None = None
    idPk: str | None = None
    labelId: str | None = None
    linkedConditionalFieldId: str | None = None
    masterConditionalFieldId: str | None = None
    tableSchemaName: str | None = None


class ReleaseReceiptVO(BaseModel):
    dataflowId: int | None = None
    id: int | None = None
    note: str | None = None


class ReleaseVO(BaseModel):
    dataProviderCode: str | None = None
    dataProviderId: int | None = None
    datasetId: int | None = None
    datasetName: str | None = None
    dateReleased: AwareDatetime | None = None
    dcrelease: bool | None = None
    eurelease: bool | None = None
    id: int | None = None
    restrictFromPublic: bool | None = None


class ReleasedDatasetDataInfoVO(BaseModel):
    collectionDatasetNumberOfRecords: int | None = None
    hasReleased: bool | None = None
    modifiedAfterRelease: bool | None = None
    reportingDatasetNumberOfRecords: int | None = None


class FieldType(StrEnum):
    TEXT = "TEXT"
    TEXTAREA = "TEXTAREA"
    LONG_TEXT = "LONG_TEXT"
    NUMBER_INTEGER = "NUMBER_INTEGER"
    NUMBER_DECIMAL = "NUMBER_DECIMAL"
    DATE = "DATE"
    DATETIME = "DATETIME"
    BOOLEAN = "BOOLEAN"
    POINT = "POINT"
    LINESTRING = "LINESTRING"
    POLYGON = "POLYGON"
    MULTIPOINT = "MULTIPOINT"
    MULTILINESTRING = "MULTILINESTRING"
    MULTIPOLYGON = "MULTIPOLYGON"
    GEOMETRYCOLLECTION = "GEOMETRYCOLLECTION"
    CODELIST = "CODELIST"
    MULTISELECT_CODELIST = "MULTISELECT_CODELIST"
    LINK = "LINK"
    EXTERNAL_LINK = "EXTERNAL_LINK"
    URL = "URL"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    ATTACHMENT = "ATTACHMENT"


class SimpleFieldSchemaVO(BaseModel):
    fieldName: str | None = None
    fieldType: FieldType | None = None


class SimpleTableSchemaVO(BaseModel):
    fields: list[SimpleFieldSchemaVO] | None = None
    tableName: str | None = None


class SnapshotVO(BaseModel):
    automatic: bool | None = None
    creationDate: AwareDatetime | None = None
    datasetId: int | None = None
    dateReleased: AwareDatetime | None = None
    description: str | None = None
    enabled: bool | None = None
    id: int | None = None
    release: bool | None = None


class StreamingResponseBody(BaseModel):
    pass


class TableSchemaIdNameVO(BaseModel):
    idTableSchema: str | None = None
    nameTableSchema: str | None = None


class Status1(StrEnum):
    IN_QUEUE = "IN_QUEUE"
    IN_PROGRESS = "IN_PROGRESS"
    CANCELED = "CANCELED"
    FINISHED = "FINISHED"


class TaskType(StrEnum):
    VALIDATION_TASK = "VALIDATION_TASK"
    IMPORT_TASK = "IMPORT_TASK"
    RELEASE_TASK = "RELEASE_TASK"
    COPY_TO_EU_DATASET_TASK = "COPY_TO_EU_DATASET_TASK"
    RESTORE_REPORTING_DATASET_TASK = "RESTORE_REPORTING_DATASET_TASK"
    RESTORE_DESIGN_DATASET_TASK = "RESTORE_DESIGN_DATASET_TASK"
    COPY_REFERENCE_DATASET_TASK = "COPY_REFERENCE_DATASET_TASK"


class TaskVO(BaseModel):
    createDate: AwareDatetime | None = None
    finishDate: AwareDatetime | None = None
    id: int | None = None
    json_: str | None = Field(None, alias="json")
    pod: str | None = None
    processId: str | None = None
    startingDate: AwareDatetime | None = None
    status: Status1 | None = None
    taskType: TaskType | None = None
    version: int | None = None


class Timestamp(BaseModel):
    date: int | None = None
    day: int | None = None
    hours: int | None = None
    minutes: int | None = None
    month: int | None = None
    nanos: int | None = None
    seconds: int | None = None
    time: int | None = None
    timezoneOffset: int | None = None
    year: int | None = None


class TruncateDataset(BaseModel):
    dataProviderId: int | None = None
    dataflowId: int | None = None
    dataflowName: str | None = None
    datasetId: int | None = None
    datasetName: str | None = None


class URI(BaseModel):
    absolute: bool | None = None
    authority: str | None = None
    fragment: str | None = None
    host: str | None = None
    opaque: bool | None = None
    path: str | None = None
    port: int | None = None
    query: str | None = None
    rawAuthority: str | None = None
    rawFragment: str | None = None
    rawPath: str | None = None
    rawQuery: str | None = None
    rawSchemeSpecificPart: str | None = None
    rawUserInfo: str | None = None
    scheme: str | None = None
    schemeSpecificPart: str | None = None
    userInfo: str | None = None


class URL(BaseModel):
    authority: str | None = None
    content: dict[str, Any] | None = None
    defaultPort: int | None = None
    file: str | None = None
    host: str | None = None
    path: str | None = None
    port: int | None = None
    protocol: str | None = None
    query: str | None = None
    ref: str | None = None
    userInfo: str | None = None


class UniqueConstraintVO(BaseModel):
    dataflowId: str | None = None
    datasetSchemaId: str | None = None
    fieldSchemaIds: list[str] | None = None
    tableSchemaId: str | None = None
    uniqueId: str | None = None


class TypeEntity(StrEnum):
    TABLE = "TABLE"
    DATASET = "DATASET"
    FIELD = "FIELD"
    RECORD = "RECORD"


class ValidationVO(BaseModel):
    id: int | None = None
    idRule: str | None = None
    levelError: LevelError | None = None
    message: str | None = None
    typeEntity: TypeEntity | None = None
    validationDate: str | None = None


class WebformVO(BaseModel):
    name: str | None = None
    type: str | None = None


class ETLDatasetVO(BaseModel):
    tables: list[ETLTableVO] | None = None


class FieldSchemaVO(BaseModel):
    codelistItems: list[str] | None = None
    description: str | None = None
    id: str | None = None
    idRecord: str | None = None
    ignoreCaseInLinks: bool | None = None
    maxSize: float | None = None
    name: str | None = None
    pk: bool | None = None
    pkHasMultipleValues: bool | None = None
    pkMustBeUsed: bool | None = None
    pkReferenced: bool | None = None
    readOnly: bool | None = None
    referencedField: ReferencedFieldSchemaVO | None = None
    required: bool | None = None
    type: Type | None = None
    validExtensions: list[str] | None = None


class InputStreamResource(BaseModel):
    description: str | None = None
    file: File | None = None
    filename: str | None = None
    inputStream: InputStream | None = None
    open: bool | None = None
    readable: bool | None = None
    uri: URI | None = None
    url: URL | None = None


class LockVO(BaseModel):
    createDate: Timestamp | None = None
    createdBy: str | None = None
    id: int | None = None
    lockCriteria: dict[str, Any] | None = None
    lockType: LockType | None = None


class RecordSchemaVO(BaseModel):
    fieldSchema: list[FieldSchemaVO] | None = None
    idRecordSchema: str | None = None


class SimpleDatasetSchemaVO(BaseModel):
    datasetName: str | None = None
    tables: list[SimpleTableSchemaVO] | None = None


class TableSchemaVO(BaseModel):
    dataAreManuallyEditable: bool | None = None
    description: str | None = None
    fixedNumber: bool | None = None
    idTableSchema: str | None = None
    nameTableSchema: str | None = None
    notEmpty: bool | None = None
    readOnly: bool | None = None
    recordSchema: RecordSchemaVO | None = None
    toPrefill: bool | None = None


class DataSetSchemaVO(BaseModel):
    availableInPublic: bool | None = None
    description: str | None = None
    idDataSetSchema: str | None = None
    nameDatasetSchema: str | None = None
    referenceDataset: bool | None = None
    tableSchemas: list[TableSchemaVO] | None = None
    webform: WebformVO | None = None


class DataSetVO(BaseModel):
    datasetValidations: list[DatasetValidationVO] | None = None
    id: int | None = None
    idDatasetSchema: str | None = None
    levelError: LevelError | None = None
    tableVO: list[TableVO] | None = None


class DatasetValidationVO(BaseModel):
    datasetValue: DataSetVO | None = None
    id: int | None = None
    validation: ValidationVO | None = None


class FieldVO(BaseModel):
    autoIncrement: bool | None = None
    byteArrayValue: Base64Str | None = None
    fieldValidations: list[FieldValidationVO] | None = None
    id: str | None = None
    idFieldSchema: str | None = None
    label: str | None = None
    levelError: LevelError | None = None
    name: str | None = None
    referenceFieldSchemaId: str | None = None
    type: Type | None = None
    value: str | None = None


class FieldValidationVO(BaseModel):
    fieldValue: FieldVO | None = None
    id: int | None = None
    validation: ValidationVO | None = None


class RecordVO(BaseModel):
    dataProviderCode: str | None = None
    datasetPartitionId: int | None = None
    fields: list[FieldVO] | None = None
    id: str | None = None
    idRecordSchema: str | None = None
    levelError: LevelError | None = None
    recordValidations: list[RecordValidationVO] | None = None
    sortCriteria: str | None = None


class RecordValidationVO(BaseModel):
    id: int | None = None
    recordValue: RecordVO | None = None
    validation: ValidationVO | None = None


class TableVO(BaseModel):
    id: int | None = None
    idTableSchema: str | None = None
    levelError: LevelError | None = None
    records: list[RecordVO] | None = None
    tableValidations: list[TableValidationVO] | None = None
    totalFilteredRecords: int | None = None
    totalRecords: int | None = None


class TableValidationVO(BaseModel):
    id: int | None = None
    tableValue: TableVO | None = None
    validation: ValidationVO | None = None


File.model_rebuild()
DataSetVO.model_rebuild()
FieldVO.model_rebuild()
RecordVO.model_rebuild()
TableVO.model_rebuild()
