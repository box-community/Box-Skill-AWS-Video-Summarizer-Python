import os
import datetime
import json

from box_sdk_gen.client import BoxClient
from box_sdk_gen.developer_token_auth import BoxDeveloperTokenAuth
from box_sdk_gen.schemas import (
    StatusSkillCard, 
    StatusSkillCardTypeField, 
    StatusSkillCardSkillCardTypeField, 
    StatusSkillCardSkillCardTitleField, 
    StatusSkillCardSkillTypeField, 
    StatusSkillCardStatusCodeField, 
    StatusSkillCardStatusField, 
    StatusSkillCardSkillField, 
    StatusSkillCardInvocationTypeField, 
    StatusSkillCardInvocationField,
    TranscriptSkillCardTypeField, 
    TranscriptSkillCardSkillCardTypeField, 
    TranscriptSkillCardSkillCardTitleField, 
    TranscriptSkillCardSkillTypeField, 
    TranscriptSkillCardSkillField, 
    TranscriptSkillCardInvocationTypeField, 
    TranscriptSkillCardInvocationField, 
    TranscriptSkillCardEntriesField, 
    TranscriptSkillCard
)
from box_sdk_gen.managers.skills import (
    UpdateAllSkillCardsOnFileStatus, 
    UpdateAllSkillCardsOnFileMetadata, 
    UpdateAllSkillCardsOnFileFileTypeField, 
    UpdateAllSkillCardsOnFileFile
)
from box_sdk_gen.utils import ByteStream

from boxsdk import OAuth2, Client
from boxsdk.object.webhook import Webhook

class box_util:

    def __init__(self, read_token, write_token, logger):
        self.logger = logger

        self.client_id = os.environ.get('BOX_CLIENT_ID', None)
        self.primary_key = os.environ.get('BOX_KEY_1', None)
        self.secondary_key = os.environ.get('BOX_KEY_2', None)

        self.read_client = self.get_basic_client(read_token)
        self.write_client = self.get_basic_client(write_token)

        self.old_client = self.get_old_client(read_token)

        self.logger.debug(f"client_id: {self.client_id} key1: {self.primary_key} key2: {self.secondary_key}")
        
    def get_basic_client(self,token):

        auth = BoxDeveloperTokenAuth(token=token)

        return BoxClient(auth)
    
    def get_old_client(self,token):

        auth = OAuth2(
            client_id=self.client_id, 
            client_secret=self.primary_key,
            access_token=token
        )

        return Client(auth)

    def is_launch_safe(self, body, headers):
        return Webhook.validate_message(body, headers, self.primary_key, self.secondary_key)
    
    def get_file_contents(self,file_id):
        
        file_content_stream: ByteStream = self.read_client.downloads.download_file(file_id=file_id)
        file_content = file_content_stream.read()

        return file_content
    
    def send_processing_card(self, file_id, skill_id, title, status, invocation_id):
        title_code = f"skill_{title.lower().replace(' ', '_')}"

        return self.write_client.skills.update_all_skill_cards_on_file(
            skill_id=skill_id,
            status=UpdateAllSkillCardsOnFileStatus.PROCESSING.value,
            file=UpdateAllSkillCardsOnFileFile(
                id=file_id,
                type=UpdateAllSkillCardsOnFileFileTypeField.FILE.value
            ), 
            metadata=UpdateAllSkillCardsOnFileMetadata(cards=[
                StatusSkillCard(
                    type=StatusSkillCardTypeField.SKILL_CARD.value, 
                    skill_card_type=StatusSkillCardSkillCardTypeField.STATUS.value, 
                    skill_card_title=StatusSkillCardSkillCardTitleField(
                        code=title_code, 
                        message=title
                    ), 
                    skill=StatusSkillCardSkillField(
                        id=skill_id, 
                        type=StatusSkillCardSkillTypeField.SERVICE.value
                    ), 
                    invocation=StatusSkillCardInvocationField(
                        id=invocation_id, 
                        type=StatusSkillCardInvocationTypeField.SKILL_INVOCATION.value
                    ), 
                    status=StatusSkillCardStatusField(
                        code=StatusSkillCardStatusCodeField.PROCESSING.value,
                        message=status
                    )
                )
            ])
        )
        

    def send_error_card(self, file_id, skill_id, title, status, invocation_id):
        
        title_code = f"skill_{title.lower().replace(' ', '_')}"
        
        return self.write_client.skills.update_all_skill_cards_on_file(
            skill_id=skill_id,
            status=UpdateAllSkillCardsOnFileStatus.PROCESSING.value,
            file=UpdateAllSkillCardsOnFileFile(
                id=file_id,
                type=UpdateAllSkillCardsOnFileFileTypeField.FILE.value
            ), 
            metadata=UpdateAllSkillCardsOnFileMetadata(cards=[
                StatusSkillCard(
                    type=StatusSkillCardTypeField.SKILL_CARD.value, 
                    skill_card_type=StatusSkillCardSkillCardTypeField.STATUS.value, 
                    skill_card_title=StatusSkillCardSkillCardTitleField(
                        code=title_code, 
                        message=title
                    ), 
                    skill=StatusSkillCardSkillField(
                        id=skill_id, 
                        type=StatusSkillCardSkillTypeField.SERVICE.value
                    ), 
                    invocation=StatusSkillCardInvocationField(
                        id=invocation_id, 
                        type=StatusSkillCardInvocationTypeField.SKILL_INVOCATION.value
                    ), 
                    status=StatusSkillCardStatusField(
                        code=StatusSkillCardStatusCodeField.TRANSIENT_FAILURE.value,
                        message=status
                    )
                )
            ])
        )
    
    def send_summary_card(self, file_id, skill_id, title, summary, invocation_id):
        title_code = f"skill_{title.lower().replace(' ', '_')}"

        return self.write_client.skills.create_box_skill_cards_on_file(
            file_id=file_id, 
            cards=[
                TranscriptSkillCard(
                    type=TranscriptSkillCardTypeField.SKILL_CARD.value, 
                    skill_card_type=TranscriptSkillCardSkillCardTypeField.TRANSCRIPT.value, 
                    skill_card_title=TranscriptSkillCardSkillCardTitleField(
                        code=title_code, 
                        message=title
                    ), 
                    skill=TranscriptSkillCardSkillField(
                        id=skill_id, 
                        type=TranscriptSkillCardSkillTypeField.SERVICE.value
                    ), 
                    invocation=TranscriptSkillCardInvocationField(
                        id=invocation_id, 
                        type=TranscriptSkillCardInvocationTypeField.SKILL_INVOCATION.value
                    ), 
                    entries=TranscriptSkillCardEntriesField(
                        text=summary
                    )
                )
            ]
        )

        
    def send_transcript_card(self, file_id, skill_id, title, transcript, invocation_id):
        title_code = f"skill_{title.lower().replace(' ', '_')}"

        return self.write_client.skills.create_box_skill_cards_on_file(
            file_id=file_id, 
            cards=[
                TranscriptSkillCard(
                    type=TranscriptSkillCardTypeField.SKILL_CARD.value, 
                    skill_card_type=TranscriptSkillCardSkillCardTypeField.TRANSCRIPT.value, 
                    skill_card_title=TranscriptSkillCardSkillCardTitleField(
                        code=title_code, 
                        message=title
                    ), 
                    skill=TranscriptSkillCardSkillField(
                        id=skill_id, 
                        type=TranscriptSkillCardSkillTypeField.SERVICE.value
                    ), 
                    invocation=TranscriptSkillCardInvocationField(
                        id=invocation_id, 
                        type=TranscriptSkillCardInvocationTypeField.SKILL_INVOCATION.value
                    ), 
                    entries=TranscriptSkillCardEntriesField(
                        text=transcript
                    )
                )
            ]
        )
        

    def delete_status_card(self, file_id):
        return self.write_client.skills.delete_box_skill_cards_from_file(file_id=file_id)