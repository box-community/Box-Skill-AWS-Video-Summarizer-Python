import base64
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
import json
import logging
import os
from pprint import pformat
from urllib.parse import parse_qsl

import box_util


sqs = boto3.client('sqs')
queue_url = os.environ['QUEUE_URL']

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

def get_file_context(body):
    
    file_context = {}

    file_context['request_id'] = body['id']
    file_context['skill_id'] = body['skill']['id']
    file_context['file_id'] = body['source']['id']
    file_context['file_name'] = body['source']['name']
    file_context['file_size'] = body['source']['size']
    file_context['file_read_token'] = body['token']['read']['access_token']
    file_context['file_write_token'] = body['token']['write']['access_token']
    
    return file_context


def lambda_handler(event, context):
    logger.debug(f"skill->lambda_handler: Event: " + pformat(event))
    logger.debug(f"skill->lambda_handler: Context: " + pformat(context))

    try:
        
        body = json.loads(event['body'])
        body_bytes = bytes(event['body'], 'utf-8')
        headers = event['headers']

        file_context = get_file_context(body)

        boxsdk = box_util.box_util(
            file_context['file_read_token'],
            file_context['file_write_token'],
            logger
        )

        if not boxsdk.is_launch_safe(body_bytes,headers):
            logger.debug("launch invalid")

            error_card = boxsdk.send_error_card(
                file_context['file_id'],
                file_context['skill_id'], 
                boxsdk.skills_error_enum['EXTERNAL_AUTH_ERROR'], 
                "File is not a video", 
                file_context['request_id']
            )
            
            return {
                "statusCode": 403,
                "body": json.dumps(str(error_card)),
                "headers": {
                    "Content-Type": "application/json",
                }
            }
        
        file_name, file_extension = os.path.splitext(file_context['file_name'])

        if not boxsdk.is_video(file_extension) and not boxsdk.is_audio(file_extension):
            logger.debug("file is not audio or video")

            error_card = boxsdk.send_error_card(
                file_context['file_id'],
                file_context['skill_id'], 
                boxsdk.skills_error_enum['INVALID_FILE_FORMAT'], 
                "File is not audio or video", 
                file_context['request_id']
            )
            
            return {
                "statusCode": 415,
                "body": json.dumps(str(error_card)),
                "headers": {
                    "Content-Type": "application/json",
                }
            }
        
        logger.debug("launch valid")

        processing_card = boxsdk.send_processing_card(
            file_context['file_id'], 
            file_context['skill_id'], 
            "Bedrock Skill", 
            "We're preparing to process your file. Please hold on!", 
            file_context['request_id']
        )

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(file_context)
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

        error_card = boxsdk.send_error_card(
            file_context['file_id'],
            file_context['skill_id'], 
            boxsdk.skills_error_enum['INVOCATIONS_ERROR'], 
            f"Error processing skill request: {e}", 
            file_context['request_id']
        )
        
        return {
            'statusCode' : 500,
            'body' : str(e),
            "headers": {
                "Content-Type": "text/plain"
            }
        }