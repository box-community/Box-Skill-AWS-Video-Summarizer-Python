import base64
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import box_util
import json
import logging
import os
from pprint import pformat
from urllib.parse import parse_qsl

sqs_client = boto3.client('sqs')
QUEUE_URL = os.environ['QUEUE_URL']

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')
logger = logging.getLogger()

if LOG_LEVEL == "DEBUG":
    logger.setLevel(logging.DEBUG)
elif LOG_LEVEL == "ERROR":
    logger.setLevel(logging.ERROR)
elif LOG_LEVEL == "WARN":
    logger.setLevel(logging.WARN)
else:
    logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.debug(f"skill->lambda_handler: Event: " + pformat(event))
    logger.debug(f"skill->lambda_handler: Context: " + pformat(context))
    logger.debug(f"skill->lambda_handler: type(body): " + str(type(event['body'])))
    logger.debug(f"skill->lambda_handler: type(headers): " + str(type(event['headers'])))

    try:
        
        body = json.loads(event['body'])
        body_bytes = bytes(event['body'], 'utf-8')
        headers = event['headers']

        boxsdk = box_util.box_util(
            body['token']['read']['access_token'],
            body['token']['write']['access_token'],
            logger
        )

        if not boxsdk.is_launch_safe(body_bytes,headers):
            logger.debug("launch invalid")

            error_card = boxsdk.send_error_card(
                body['source']['id'],
                body['skill']['id'], 
                "Bedrock Skill", 
                "Invalid launch detected", 
                body['id']
            )
            
            return {
                "statusCode": 403,
                "body": json.dumps(error_card),
                "headers": {
                    "Content-Type": "application/json",
                }
            }
        
        logger.debug("launch valid")

        download_url = boxsdk.get_download_url(body['source']['id'])

        logger.debug(f"download url is {download_url}")

        processing_card = boxsdk.send_processing_card(
            body['source']['id'], 
            body['skill']['id'], 
            "Bedrock Skill", 
            "We're preparing to process your file. Please hold on!", 
            body['id']
        )

        return {
            "statusCode": 200,
            "body": json.dumps(str(processing_card)),
            "headers": {
                "Content-Type": "application/json",
            }
        }
        
    except Exception as e:
        logger.exception(f"skill: Exception: {e}")
        return {
            'statusCode' : 500,
            'body' : str(e),
            "headers": {
                "Content-Type": "text/plain"
            }
        }