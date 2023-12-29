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
import ai_util

dynamodb = boto3.resource('dynamodb', region_name="us-east-1")

JOB_TABLE = os.environ['JOB_TABLE']
job_table= dynamodb.Table(JOB_TABLE)

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

def write_job(job_id, file_context):
    
    try:
        response = job_table.put_item(
            Item={
                'job_id': str(job_id),
                'request_id': file_context['request_id'],
                'skill_id': file_context['skill_id'],
                'file_id': file_context['file_id'],
                'file_name': file_context['file_name'],
                'file_size': file_context['file_size'],
                'file_read_token': file_context['file_read_token'],
                'file_write_token': file_context['file_write_token'],
            }
        )
        logger.info(f"Job {job_id} successfully added")
    except ClientError as err:
        logger.exception(
            f"Couldn't write data: job_id {job_id}. Here's why: {err.response['Error']['Code']}: {err.response['Error']['Message']}",
        )
        raise
    except Exception as e:
        logger.exception(f"Error writing job_id {job_id} - {e}")

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
                "Bedrock Skill", 
                "Invalid launch detected", 
                file_context['request_id']
            )
            
            return {
                "statusCode": 403,
                "body": json.dumps(str(error_card)),
                "headers": {
                    "Content-Type": "application/json",
                }
            }
        
        logger.debug("launch valid")

        download_url = boxsdk.get_download_url(file_context['file_id'])

        logger.debug(f"download url is {download_url}")

        processing_card = boxsdk.send_processing_card(
            file_context['file_id'], 
            file_context['skill_id'], 
            "Bedrock Skill", 
            "We're preparing to process your file. Please hold on!", 
            file_context['request_id']
        )

        ai = ai_util.ai_util()

        job_id = ai.meeting_transcribe(download_url, file_context['file_name'])

        write_job(job_id, file_context)

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