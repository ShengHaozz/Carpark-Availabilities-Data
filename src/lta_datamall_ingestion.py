import boto3
import urllib.request
import os
from datetime import datetime, timezone

ACCOUNT_KEY = os.environ["ACCOUNT_KEY"]
BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2"
LEVEL = os.environ["LEVEL"]
SOURCE = os.environ["SOURCE"]

headers = {
    "AccountKey" : ACCOUNT_KEY
}

def handler(event, context):
    s3 = boto3.client("s3")
    req = urllib.request.Request(
        ENDPOINT,
        headers = headers
    )

    with urllib.request.urlopen(req) as response:
        response_bytes = response.read()
    
    now = datetime.now(timezone.utc)
    
    key = (
        f"level={LEVEL}/"
        f"source={SOURCE}/"
        f"year={now.year}/"
        f"month={now.month:02d}/"
        f"day={now.day:02d}/"
        f"hour={now.hour:02d}/"
        f"data.json"
    )
    s3.put_object(
        Bucket =  BUCKET,
        key = key,
        Body = response_bytes,
        ContentType = "application/json"
    )