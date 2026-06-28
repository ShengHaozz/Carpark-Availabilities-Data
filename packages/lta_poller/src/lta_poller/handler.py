import boto3
import urllib.request
from urllib.error import HTTPError
import os
from datetime import datetime, timezone, timedelta
import json
import time

ACCOUNT_KEY = os.environ["ACCOUNT_KEY"]
BUCKET = os.environ["BUCKET_NAME"]
ENDPOINT = "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2?$skip={}"
LEVEL = os.environ["LEVEL"]
SOURCE = os.environ["SOURCE"]
MAX_TRIES = 3
headers = {
    "AccountKey" : ACCOUNT_KEY
}

def handler(event, context):
    s3 = boto3.client("s3")

    values = []
    poll_start = datetime.now(timezone.utc)
    page = 1
    tries = 1
    
    while page < 10: # max 10 skips, but break when return is None
        
        if tries > MAX_TRIES:
            print(f"Exceeded {MAX_TRIES}, skipping page {page}")
            page += 1
            continue
        
        print(f"Attempt {tries} of page {page}")

        try:  
            req = urllib.request.Request(
                ENDPOINT.format(page * 500), # skip in units of 500
                headers = headers
            )
            with urllib.request.urlopen(req) as response:
                data: dict = json.load(response)
        
        except HTTPError as e:
            print(f"HTTP {e.code}: {e.reason}")
            
            if e.code == 429: # Rate Limit Exceeded
                retry_after_s = e.headers.get("Retry-After", 10 * (tries ** 2))
                print(f"Retrying after {retry_after_s}s")
                time.sleep(retry_after_s)
                tries += 1
            else:
                page += 1
                tries = 1
            
            continue

        except Exception as e:
            print(f"Exception occured: {e}")
            retry_after_s = 10 * (tries ** 2)
            print(f"Retrying after {retry_after_s}s")
            time.sleep(retry_after_s)
            tries += 1
            continue


        if not data["value"]:
            page -= 1 # revert to last page
            break
            
        values.extend(data["value"])

        page += 1

            
    poll_end = datetime.now(timezone.utc)  
    
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

    snapshot = {
        "datetime" : ref_date.isoformat(),
        "source" : SOURCE,
        "poll_start" : poll_start.isoformat(),
        "poll_end" : poll_end.isoformat(),
        "pages" : page,
        "records_count" : len(values),
        "value" : values
    }
    try: 
        s3.put_object(
            Bucket =  BUCKET,
            Key = key,
            Body = json.dumps(snapshot),
            ContentType = "application/json"
        )
        print(f"Uploaded {key}")
    except Exception as e:
        print(f"Error occured for key {key}: {e}")
