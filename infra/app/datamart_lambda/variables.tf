variable "s3_bucket" {
  description = "The main data S3 bucket"
  type = object({
    id  = string
    arn = string
  })
}
