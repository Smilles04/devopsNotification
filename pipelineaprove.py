# This function is triggered via API Gateway when a user acts on the Slack interactive message sent by approval requester.

from urllib.parse import parse_qs
import os
import json
import logging
import boto3

SLACK_VERIFICATION_TOKEN = os.environ['SLACK_VERIFICATION_TOKEN']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Triggered by API Gateway
# It kicks off a particular CodePipeline project
def handler(event, context):
    body = parse_qs(event['body'])
    payload = json.loads(body['payload'][0])
    response = {
        'text': payload['original_message']['text'],
        'attachments': [
            {
                'text': payload['original_message']['attachments'][0]['text'],
                'fallback': 'Unable to approve the change',
                'callback_id': 'wopr_game',
                'color': '#3AA3E3',
                'attachment_type': 'default',
                'fields': []
            }
        ]
    }
    # Validate Slack token
    if SLACK_VERIFICATION_TOKEN == payload['token']:
        result = process_action(json.loads(payload['actions'][0]['value']))
        
        # This will replace the interactive message with a simple text response.
        # You can implement a more complex message update if you would like.
        if result == 'internal_error':
            response['attachments'][0]['color'] = 'warning'
            response['attachments'][0]['fields'].append({
                'value': 'There was an error processing the approval'
            })
            return {
                'isBase64Encoded': 'false',
                'statusCode': 500,
                'body': json.dumps(response)
            }
        elif result == 'already_completed':
            response['attachments'][0]['fields'].append({
                'value': 'The approval has already been completed in CodePipeline'
            })
            return {
                'isBase64Encoded': 'false',
                'statusCode': 200,
                'body': json.dumps(response)
            }
        else:
            response['attachments'][0]['color'] = 'good' if result == 'Approved' else 'danger'
            response['attachments'][0]['fields'].append({
                'value': result + ' by <@' + payload['user']['id'] + '>'
            })
            return {
                'isBase64Encoded': 'false',
                'statusCode': 200,
                'body': json.dumps(response)
            }
    else:
        response['attachments'][0]['color'] = 'warning'
        response['attachments'][0]['fields'].append({
            'value': 'This request does not include a vailid verification token'
        })
        return {
            'isBase64Encoded': 'false',
            'statusCode': 403,
            'body': json.dumps(response)
        }
    
def process_action(action_details):
    codepipeline_status = 'Approved' if action_details['approve'] else 'Rejected'
    codepipeline_token = action_details['codePipelineToken']
    codepipeline_name = action_details['codePipelineName']
    codepipeline_stage = action_details['codePipelineStage']
    codepipeline_action = action_details['codePipelineAction']
    
    client = boto3.client('codepipeline')
    try:
        response_approval = client.put_approval_result(
            pipelineName=codepipeline_name,
            stageName=codepipeline_stage,
            actionName=codepipeline_action,
            result={
                'summary': '',
                'status': codepipeline_status
            },
            token=codepipeline_token
        )
        return codepipeline_status
    except Exception as error:
        if type(error).__name__ == 'ApprovalAlreadyCompletedException':
            return 'already_completed'
        else:
            print(repr(error))
            return 'internal_error'