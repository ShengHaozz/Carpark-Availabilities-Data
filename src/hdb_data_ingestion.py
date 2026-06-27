import boto3
import urllib.request
from urllib.error import HTTPError
import os
from datetime import datetime, timezone, timedelta
import time

BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = "https://api.data.gov.sg/v1/transport/carpark-availability"
LEVEL = os.environ["LEVEL"]
SOURCE = os.environ["SOURCE"]
MAX_TRIES = 3

def handler(event, context):
    s3 = boto3.client("s3")

    req = urllib.request.Request(
        ENDPOINT
    )

    tries = 1

    poll_start = datetime.now(timezone.utc)

    for _ in range(5):
        if tries > MAX_TRIES:
            print(f"Exceeded {MAX_TRIES}, skipping")
            return
        
        print(f"Attempt {tries}")

        try:  
            req = urllib.request.Request(
                ENDPOINT
            )
            with urllib.request.urlopen(req) as response:
                raw_response = response.read()
        
        except HTTPError as e:
            print(f"HTTP {e.code}: {e.reason}")
            
            if e.code == 429: # Rate Limit Exceeded
                retry_after_s = e.headers.get("Retry-After", 10 * (tries ** 2))
                print(f"Retrying after {retry_after_s}s")
                time.sleep(retry_after_s)
                tries += 1
                continue

            return
            

        except Exception as e:
            print(f"Exception occured: {e}")
            retry_after_s = 10 * (tries ** 2)
            print(f"Retrying after {retry_after_s}s")
            time.sleep(retry_after_s)
            tries += 1
            continue
    
    poll_start = datetime.now(timezone.utc)


    
    ref_date = poll_start - timedelta(
        minutes = poll_start.minute % 10,
        seconds = poll_start.second,
        microseconds = poll_start.microsecond
    ) # floor to 10 minutes
    
    key = (
        f"level={LEVEL}/"
        f"source={SOURCE}/"
        f"year={ref_date.year}/"
        f"month={ref_date.month:02d}/"
        f"day={ref_date.day:02d}/"
        f"hour={ref_date.hour:02d}/"
        f"snapshot_{ref_date.isoformat()}.json"
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
