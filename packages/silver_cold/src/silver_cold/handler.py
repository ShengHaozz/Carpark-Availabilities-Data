import boto3
from models import DatamallCarparkAvailability, HDBCarparkData, SilverColdCarparkSnapshot
import os
import json

BUCKET = os.environ["BUCKET_NAME"]
INPUT_LEVEL = os.environ["INPUT_LEVEL"]
LTA_SOURCE = os.environ["LTA_SOURCE"]
HDB_SOURCE = os.environ["HDB_SOURCE"]
OUTPUT_LEVEL = os.environ["OUTPUT_LEVEL"]

KEY_PREFIX = (
    "level={level}/"
    "source={source}/"
    "year={year:02d}/"
    "month={month:02d}/"
    "day={day:02d}/"
)

"""
event = {
    year: int,
    month: int,
    day: int
}
"""

def handler(event, context):
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')

    lta_key_prefix = KEY_PREFIX.format(
        level = INPUT_LEVEL,
        source = LTA_SOURCE,
        year = event["year"],
        month = event["month"],
        day = event["day"]
    )

    for lta_page in paginator.paginate(Bucket = BUCKET, Prefix = lta_key_prefix):
        for obj in lta_page.get("Content", []):
            path = obj["Key"]

            if path.endswith('/'): # placeholder directories
                continue

            response = s3.get_object(
                Bucket = BUCKET,
                Key = path
            )

            with response['Body'] as body:
                data = json.loads(body.read())
            
            lta_snapshot = DatamallCarparkAvailability.model_validate(data)