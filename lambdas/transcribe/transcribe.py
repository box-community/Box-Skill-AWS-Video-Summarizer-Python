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

"""
dynamodb = boto3.resource('dynamodb', region_name="us-east-1")

TABLE_NAME = os.environ['TABLE_NAME']
config_table= dynamodb.Table(TABLE_NAME)

CACHE_NAME = os.environ['CACHE_NAME']
cache = dynamodb.Table(CACHE_NAME)
"""

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
    logger.debug(f"transcribe->lambda_handler: Event: " + pformat(event))
    logger.debug(f"trnscribe->lambda_handler: Context: " + pformat(context))
    return {
        'statusCode' : 200
    }