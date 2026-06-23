import os

def main():
    print("Hello World!")
    print(f"Bucket: {os.environ["BUCKET_NAME"]}")

def handler(event, context):
    print(f"Event: {event}")
    main()