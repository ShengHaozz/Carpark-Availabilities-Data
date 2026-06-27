import boto3
import urllib.request
import os
from datetime import datetime, timezone

BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = "https://api.data.gov.sg/v1/transport/carpark-availability"
LEVEL = os.environ["LEVEL"]
SOURCE = os.environ["SOURCE"]

def handler(event, context):
    s3 = boto3.client("s3")

    req = urllib.request.Request(
        ENDPOINT
    )

    with urllib.request.urlopen(req) as response:
        raw_response = response.read()
    
    now = datetime.now(timezone.utc)
    
    key = (
        f"level={LEVEL}/"
        f"source={SOURCE}/"
        f"year={now.year}/"
        f"month={now.month:02d}/"
        f"day={now.day:02d}/"
        f"hour={now.hour:02d}/"
        f"minute={((now.minute // 10) * 10):02d}/" # floor to 10s
        f"data.json"
    )

    try: 
        s3.put_object(
            Bucket =  BUCKET,
            Key = key,
            Body = raw_response,
            ContentType = "application/json"
        )
        print(f"Uploaded {key}")
    except Exception as e:
        print(f"Error occured for key {key}: {e}")
