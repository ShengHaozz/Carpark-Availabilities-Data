import boto3
import urllib.request
import os
from datetime import datetime, timezone
import json

ACCOUNT_KEY = os.environ["ACCOUNT_KEY"]
BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2?$skip={}"
LEVEL = os.environ["LEVEL"]
SOURCE = os.environ["SOURCE"]

headers = {
    "AccountKey" : ACCOUNT_KEY
}

def handler(event, context):
    s3 = boto3.client("s3")

    for i in range(10): # max 10 skips, but break when return is None
        
        req = urllib.request.Request(
            ENDPOINT.format(i * 500), # skip in units of 500
            headers = headers
        )

        with urllib.request.urlopen(req) as response:
            data: dict = json.load(response)
        
        if not data["value"]:
            break
        
        now = datetime.now(timezone.utc)
        
        key = (
            f"level={LEVEL}/"
            f"source={SOURCE}/"
            f"year={now.year}/"
            f"month={now.month:02d}/"
            f"day={now.day:02d}/"
            f"hour={now.hour:02d}/"
            f"minute={((now.minute // 10) * 10):02d}" # floor to 10s
            f"data_skip_{(i * 500):04d}.json"
        )
        try: 
            s3.put_object(
                Bucket =  BUCKET,
                Key = key,
                Body = json.dumps(data),
                ContentType = "application/json"
            )
            print(f"Uploaded {key}")
        except Exception as e:
            print(f"Error occured for key {key}: {e}")
