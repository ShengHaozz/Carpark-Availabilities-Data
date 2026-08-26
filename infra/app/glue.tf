resource "aws_glue_catalog_database" "silver" {
  name        = "silver"
  description = "Glue Catalog database for Silver Layer parquet tables"
}

resource "aws_glue_catalog_database" "prod_staging" {
  name        = "prod_staging"
  description = "Glue Catalog database for Gold Staging Layer views"
}

resource "aws_glue_catalog_database" "prod_gold" {
  name        = "prod_gold"
  description = "Glue Catalog database for Gold Layer dimensional Iceberg tables"
}

resource "aws_glue_catalog_table" "silver_cold" {
  name          = "silver_cold"
  database_name = aws_glue_catalog_database.silver.name
  table_type    = "EXTERNAL_TABLE"
  description   = "External table mapping to silver cold partitioned parquet files in S3 with Partition Projection"

  parameters = {
    "EXTERNAL"            = "TRUE"
    "parquet.compression" = "ZSTD"
    "classification"      = "parquet"
    "projection.enabled"  = "true"

    "projection.year.type"  = "integer"
    "projection.year.range" = "2024,2035"

    "projection.month.type"   = "integer"
    "projection.month.range"  = "1,12"
    "projection.month.digits" = "2"

    "projection.day.type"   = "integer"
    "projection.day.range"  = "1,31"
    "projection.day.digits" = "2"

    "storage.location.template" = "s3://${aws_s3_bucket.bucket.id}/level=silver/year=$${year}/month=$${month}/day=$${day}"
  }

  partition_keys {
    name = "year"
    type = "int"
  }

  partition_keys {
    name = "month"
    type = "int"
  }

  partition_keys {
    name = "day"
    type = "int"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.bucket.id}/level=silver/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "ParquetHiveSerDe"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
      parameters = {
        "serialization.format" = "1"
      }
    }

    columns {
      name = "carpark_id"
      type = "string"
    }

    columns {
      name = "snapshot_timestamp"
      type = "timestamp"
    }

    columns {
      name = "lot_type"
      type = "string"
    }

    columns {
      name = "lots_available"
      type = "int"
    }

    columns {
      name = "total_lots"
      type = "int"
    }

    columns {
      name = "location_latitude"
      type = "double"
    }

    columns {
      name = "location_longitude"
      type = "double"
    }

    columns {
      name = "area"
      type = "string"
    }

    columns {
      name = "development"
      type = "string"
    }

    columns {
      name = "agency"
      type = "string"
    }

    columns {
      name = "ingestion_timestamp"
      type = "timestamp"
    }

    columns {
      name = "source_filepath"
      type = "string"
    }
  }
}

