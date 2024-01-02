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

s3 = boto3.client('s3')
storage_bucket = os.environ['STORAGE_BUCKET']

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

    file_context['request_id'] = body['request_id']
    file_context['skill_id'] = body['skill_id']
    file_context['file_id'] = body['file_id']
    file_context['file_name'] = body['file_name']
    file_context['file_size'] = body['file_size']
    file_context['file_read_token'] = body['file_read_token']
    file_context['file_write_token'] = body['file_write_token']
    
    return file_context

def upload_file(file_name, file_contents):
    decode_content = base64.b64decode(file_contents)

    s3_upload = s3.put_object(Bucket=storage_bucket,Key=file_name,Body=decode_content)

    logger.debug(f"s3_upload {s3_upload}")

    return s3_upload

def write_job(job_id, job_uri, file_context):
    
    try:
        response = job_table.put_item(
            Item={
                'job_id': str(job_id),
                'job_uri': str(job_uri),
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
    logger.debug(f"transcribe->lambda_handler: Event: " + pformat(event))
    logger.debug(f"transcribe->lambda_handler: Context: " + pformat(context))

    try:
        
        for record in event['Records']:
            body = record['body']

            logger.debug("Body: " + str(body))

            data = json.loads(body)
    
            file_context = get_file_context(data)
            file_context['sqs_message_id'] = record['messageId']

            boxsdk = box_util.box_util(
                file_context['file_read_token'],
                file_context['file_write_token'],
                logger
            )

            file_content = boxsdk.get_file_contents(file_context['file_id'])

            upload = upload_file(file_context['file_name'], file_content)

            logger.debug(f"upload results: {upload}")

            ai = ai_util.ai_util()

            job_id, job_uri = ai.meeting_transcribe(file_context['file_name'])

            write_job(job_id, job_uri, file_context)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Transcription started"}),
            "headers": {
                "Content-Type": "application/json",
            }
        }
        
    except Exception as e:
        logger.exception(f"transcribe: Exception: {e}")
        return {
            'statusCode' : 200,
            'body' : str(e),
            "headers": {
                "Content-Type": "text/plain"
            }
        }