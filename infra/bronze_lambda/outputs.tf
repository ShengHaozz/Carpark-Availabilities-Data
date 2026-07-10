output "functions" {
  value = {
    lta_datamall = aws_lambda_function.datamall_ingestion_lambda
    hdb_data     = aws_lambda_function.hdb_data_ingestion
  }
}

