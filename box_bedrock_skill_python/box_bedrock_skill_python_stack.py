#!/usr/bin/env python3
from aws_cdk import (
    core as cdk,
    aws_lambda as _lambda, 
    aws_apigateway as _apigw, 
    aws_apigatewayv2 as _apigw2, 
    aws_apigatewayv2_integrations as _a2int,
    aws_apigatewayv2_authorizers as _a2auth,
    aws_dynamodb as _dynamo,
    custom_resources as _resources,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_s3_assets as s3assets,
    aws_route53 as route53,
    aws_route53_targets as alias,
    aws_certificatemanager as acm,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_lambda_event_sources as ales,
    aws_ec2 as ec2,
    aws_elasticache as cache,
    aws_lambda_python as lambpy,
    aws_kms as kms,
    aws_secretsmanager as secretsmanager,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2
)

import json

from app_config import box_config, app_config, ai_config

class BoxBedrockSkillPythonStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        """
        f = open('box_config.json')
        
        box_config = json.load(f)

        f2 = open("lambdas/lti_validation/private.pem", "a")
        f2.write(box_config['boxAppSettings']['appAuth']['privateKey'])
        f2.close()
        """
       
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
        
        box_gen_lambda_layer = lambpy.PythonLayerVersion(
            self, 'transcriptionGenBoxLayer',
            entry='box_sdk_gen',
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_8],
            description='transcription Box Gen layer',
            layer_version_name='transcriptionGenBoxLayer'
        )
        
        box_lambda_layer = lambpy.PythonLayerVersion(
            self, 'transcriptionBoxLayer',
            entry='boxsdk',
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_8],
            description='transcription Box layer',
            layer_version_name='transcriptionBoxLayer'
        )

        skill_lambda = lambpy.PythonFunction(
            self, "skillLambda",
            entry="lambdas/skill",
            index="skill.py",
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="lambda_handler",
            layers=[box_gen_lambda_layer,box_lambda_layer],
            timeout=cdk.Duration.minutes(15),
            environment = {
                "LOG_LEVEL": app_config['LOG_LEVEL'],
                "BOX_CLIENT_ID": box_config['BOX_CLIENT_ID'],
                "BOX_KEY_1": box_config['BOX_KEY_1'],
                "BOX_KEY_2": box_config['BOX_KEY_2'],
                "BUCKET_NAME": transcription_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
            }
        )

        summarize_lambda =  lambpy.PythonFunction(
            self, "summarizeLambda",
            entry="lambdas/summarize",
            index="summarize.py",
            runtime=_lambda.Runtime.PYTHON_3_8,
            handler="lambda_handler",
            layers=[box_gen_lambda_layer,box_lambda_layer],
            timeout=cdk.Duration.minutes(15),
            environment = {
                "LOG_LEVEL": app_config['LOG_LEVEL'],
                "BUCKET_NAME": transcription_bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "AI_MODEL": ai_config['MODEL_ID']
            }
        )

        summarize_source = ales.S3EventSource(
            transcription_bucket, 
            events= [
                s3.EventType.OBJECT_CREATED_PUT
            ]
        )
        summarize_lambda.add_event_source(summarize_source)

        job_table.grant_full_access(skill_lambda)
        job_table.grant_full_access(summarize_lambda)

        transcription_bucket.grant_read_write(summarize_lambda)

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

