#!/usr/bin/env python3
import aws_cdk as cdk
from aws_cdk import (
    Size,
    aws_lambda as _lambda, 
    aws_apigateway as _apigw, 
    aws_apigatewayv2 as _apigw2, 
    aws_apigatewayv2_integrations as _a2int,
    aws_apigatewayv2_authorizers as _a2auth,
    aws_dynamodb as _dynamo,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_lambda_event_sources as ales,
    aws_logs as logs,
    aws_lambda_python_alpha as _lambpy,
    aws_iam as _iam
)
from constructs import Construct
import json

from app_config import box_config, app_config, ai_config

class BoxBedrockSkillPythonStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
       
        lambda_custom_policy = _iam.PolicyDocument(
            assign_sids=False,
            statements=[
                _iam.PolicyStatement(
                    effect=_iam.Effect.ALLOW,
                    # principals=[_iam.AccountRootPrincipal()],
                    actions=[
                        's3:*',
                        'kms:*',
                        'transcribe:*',
                        'iam:PassRole',
                        'logs:CreateLogGroup',
                        'logs:CreateLogStream',
                        'logs:PutLogEvents',
                        'bedrock:*'
                    ],
                    resources=["*"]
                )
        ])

        lambda_role = _iam.Role(scope=self, id='cdk-lambda-role',
            assumed_by =_iam.ServicePrincipal('lambda.amazonaws.com'),
            role_name=f"box-skills-lambda-role",
            description="box-skills-lambda-role",
            inline_policies= { "lambda_custom_policy": lambda_custom_policy },
            managed_policies=[
            _iam.ManagedPolicy.from_aws_managed_policy_name(
                'service-role/AWSLambdaBasicExecutionRole'
            )]
        )

        transcribe_queue = sqs.Queue(
            self, "transcribeQueue",
            queue_name="TranscribeQueue",
            visibility_timeout=cdk.Duration.minutes(15),
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        storage_bucket = s3.Bucket(
            self, 'storageBucket',
            bucket_name="box-bedrock-storage-bucket",
            public_read_access=False,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        transcription_bucket = s3.Bucket(
            self, 'transcriptionBucket',
            bucket_name="box-bedrock-transcription-bucket",
            public_read_access=False,
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        
        job_table = _dynamo.Table(
            self, id="jobTable",
            table_name="transcriptionJobTable",
            partition_key=_dynamo.Attribute(name="job_id", type=_dynamo.AttributeType.STRING),
            removal_policy=cdk.RemovalPolicy.DESTROY,
            encryption=_dynamo.TableEncryption.AWS_MANAGED
        )
        
        box_gen_lambda_layer = _lambpy.PythonLayerVersion(
            self, 'transcriptionGenBoxLayer',
            entry='box_sdk_gen',
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description='transcription Box Gen layer',
            layer_version_name='transcriptionGenBoxLayer'
        )
        
        box_lambda_layer = _lambpy.PythonLayerVersion(
            self, 'transcriptionBoxLayer',
            entry='boxsdk',
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description='transcription Box layer',
            layer_version_name='transcriptionBoxLayer'
        )

        skill_lambda = _lambpy.PythonFunction(
            self, "skillLambda",
            entry="lambdas/skill",
            index="skill.py",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_handler",
            layers=[box_gen_lambda_layer,box_lambda_layer],
            timeout=cdk.Duration.minutes(15),
            role=lambda_role,
            environment = {
                "LOG_LEVEL": app_config['LOG_LEVEL'],
                "BOX_CLIENT_ID": box_config['BOX_CLIENT_ID'],
                "BOX_KEY_1": box_config['BOX_KEY_1'],
                "BOX_KEY_2": box_config['BOX_KEY_2'],
                "QUEUE_URL": transcribe_queue.queue_url
            }
        )

        transcribe_lambda = _lambpy.PythonFunction(
            self, "transcribeLambda",
            entry="lambdas/transcribe",
            index="transcribe.py",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_handler",
            layers=[box_gen_lambda_layer,box_lambda_layer],
            timeout=cdk.Duration.minutes(15),
            role=lambda_role,
            ephemeral_storage_size=Size.gibibytes(10),
            memory_size=10240,
            environment = {
                "LOG_LEVEL": app_config['LOG_LEVEL'],
                "BOX_CLIENT_ID": box_config['BOX_CLIENT_ID'],
                "BOX_KEY_1": box_config['BOX_KEY_1'],
                "BOX_KEY_2": box_config['BOX_KEY_2'],
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "TRANSCRIBE_BUCKET": transcription_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "QUEUE_URL": transcribe_queue.queue_url
            }
        )

        summarize_lambda =  _lambpy.PythonFunction(
            self, "summarizeLambda",
            entry="lambdas/summarize",
            index="summarize.py",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambda_handler",
            layers=[box_gen_lambda_layer,box_lambda_layer],
            timeout=cdk.Duration.minutes(15),
            role=lambda_role,
            ephemeral_storage_size=Size.gibibytes(10),
            environment = {
                "LOG_LEVEL": app_config['LOG_LEVEL'],
                "STORAGE_BUCKET": storage_bucket.bucket_name,
                "TRANSCRIBE_BUCKET": transcription_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "AI_MODEL": ai_config['MODEL_ID']
            }
        )

        transcribe_source = ales.SqsEventSource(transcribe_queue)
        transcribe_lambda.add_event_source(transcribe_source)

        summarize_source = ales.S3EventSource(
            transcription_bucket, 
            events= [
                s3.EventType.OBJECT_CREATED_PUT
            ],
            filters=[
                s3.NotificationKeyFilter(prefix="meetings_summary/")
            ]
        )
        summarize_lambda.add_event_source(summarize_source)

        job_table.grant_full_access(transcribe_lambda)
        job_table.grant_full_access(summarize_lambda)

        storage_bucket.grant_read_write(transcribe_lambda)
        storage_bucket.grant_read_write(summarize_lambda)
        transcription_bucket.grant_read_write(summarize_lambda)

        transcribe_queue.grant_send_messages(skill_lambda)
        transcribe_queue.grant_consume_messages(transcribe_lambda)
        transcribe_queue.grant_purge(transcribe_lambda)

        # Define API Gateway and HTTP API
        transcribe_api = _apigw.RestApi(
            self, 'SkillGateway'
        )

        skill_resource = transcribe_api.root.add_resource(
            'skill',
            default_cors_preflight_options=_apigw.CorsOptions(
                allow_methods=['POST'],
                allow_origins=_apigw.Cors.ALL_ORIGINS)
        )

        skill_lambda_integration = _apigw.LambdaIntegration(
            skill_lambda,
            proxy=True,
            integration_responses=[
                _apigw.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': "'*'"
                    }
                )
            ]
        )

        skill_resource.add_method(
            'POST', skill_lambda_integration,
            method_responses=[
                _apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Origin': True
                    }
                )
            ]
        )
        
        cdk.CfnOutput(self, "Deployment Stage", value=str(transcribe_api.deployment_stage.to_string()))
        cdk.CfnOutput(self, "URL", value=transcribe_api.url)
        cdk.CfnOutput(self, "OIDC Login Endpoint: ", value=skill_resource.path)

