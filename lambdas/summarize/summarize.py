import base64
from urllib.parse import parse_qsl
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import json
import logging
import os
from pprint import pformat
import uuid

import ai_util,box_util

dynamodb = boto3.resource('dynamodb')

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

def get_job_data(job_id):
    results = job_table.query(KeyConditionExpression=Key("job_id").eq(job_id))
    
    job_data = {}
    
    try:
        item = results['Items'][0]
        logger.debug("item: " + str(item))

        """
        'job_id': str(job_id),
        'job_uri': str(job_uri),
        'request_id': file_context['request_id'],
        'skill_id': file_context['skill_id'],
        'file_id': file_context['file_id'],
        'file_name': file_context['file_name'],
        'file_size': file_context['file_size'],
        'file_read_token': file_context['file_read_token'],
        'file_write_token': file_context['file_write_token'],
        """
        
        job_data['job_id'] = item['job_id']
        job_data['job_uri'] =  item['job_uri']
        job_data['request_id'] =  item['request_id']
        job_data['skill_id'] =  item['skill_id']
        job_data['file_id'] =  item['file_id']
        job_data['file_name'] =  item['file_name']
        job_data['file_size'] =  item['file_size']
        job_data['file_read_token'] =  item['file_read_token']
        job_data['file_write_token'] =  item['file_write_token']
        logger.debug("job_data: " + str(job_data))
        
    except Exception as e:
        logger.error(str(e))
        logger.error(job_id + ' is not defined.')

    return job_data


def delete_job_data(job_id):
    job_table.delete_item(
        Key={
            'job_id': job_id
        }
    )

def lambda_handler(event, context):
    logger.debug(f"summarize->lambda_handler: Event: " + pformat(event))
    logger.debug(f"summarize->lambda_handler: Context: " + pformat(context))

    try:


        ai = ai_util.ai_util()

        for record in event['Records']:

            s3_key = record['s3']['object']['key']
            
            if s3_key == 'meetings_summary/.write_access_check_file.temp':
                logger.info(f"Received trigger for transcribe's permission check. Ignoring...")
                return {
                    'statusCode' : 200
                }
            
            meeting_file = s3_key.replace("meetings_summary/","").replace(".json", "")

            transcription = ai.get_transcription(meeting_file)

            logger.debug(f"transcription {transcription}")

            summary = ai.meeting_summarize(transcription,meeting_file)

            logger.debug(f"summary {summary}")

            job_data = get_job_data(meeting_file)

            box = box_util.box_util(
                job_data['file_read_token'],
                job_data['file_write_token'],
                logger    
            )

            delete_cards = box.delete_status_card(job_data['file_id'])

            summary_sent = box.update_skills_on_file(
                job_data['file_id'],
                job_data['skill_id'],
                str(transcription),
                str(summary),
                job_data['request_id']
            )
            
            logger.debug(f"summary sent {summary_sent}")

            """transcript_sent = box.send_transcript_card(
                job_data['file_id'],
                job_data['skill_id'],
                "Video Transcript",
                str(transcription),
                job_data['request_id']
            )
            
            logger.debug(f"transcript sent {transcript_sent}")"""


            delete_job_data(meeting_file)

        return {
            'statusCode' : 200
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