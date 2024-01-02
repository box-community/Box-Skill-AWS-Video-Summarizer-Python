import os
import datetime
import json

from box_sdk_gen.client import BoxClient
from box_sdk_gen.developer_token_auth import BoxDeveloperTokenAuth
from box_sdk_gen.schemas import StatusSkillCard, StatusSkillCardTypeField, StatusSkillCardSkillCardTypeField, StatusSkillCardSkillCardTitleField, StatusSkillCardSkillTypeField, StatusSkillCardStatusCodeField, StatusSkillCardStatusField, StatusSkillCardSkillField, StatusSkillCardInvocationTypeField, StatusSkillCardInvocationField 
from box_sdk_gen.managers.skills import SkillsManager, UpdateBoxSkillCardsOnFileRequestBodyOpField, UpdateBoxSkillCardsOnFileRequestBody, UpdateAllSkillCardsOnFileStatus, UpdateAllSkillCardsOnFileMetadata, UpdateAllSkillCardsOnFileFileTypeField, UpdateAllSkillCardsOnFileFile, UpdateAllSkillCardsOnFileFileVersionTypeField, UpdateAllSkillCardsOnFileFileVersion, UpdateAllSkillCardsOnFileUsage
from box_sdk_gen.utils import ByteStream

from boxsdk import OAuth2, Client, JWTAuth
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
        
        chunk = file_content_stream.read(1024)
        file_content = chunk

        while chunk is not None:
            chunk = file_content_stream.read(1024)
            file_content += chunk

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


    def jwt_auth(self):
        try:
            auth = JWTAuth(
                client_id=os.environ['BOX_CLIENT_ID'],
                client_secret=os.environ['BOX_CLIENT_SECRET'],
                enterprise_id=os.environ['BOX_CLIENT_EID'],
                jwt_key_id=os.environ['BOX_JWT_KEY'],
                rsa_private_key_file_sys_path=os.environ['BOX_PRIVATE_KEY'],
                rsa_private_key_passphrase=os.environ['BOX_PRIVATE_KEY_PASSPHRASE'],
            )

            self.access_token = auth.authenticate_instance()

            self.logger.debug("instantiate client")
            self.client = Client(auth)
        except Exception as e:
            self.logger.exception(f"Unable to instantiate Box SDK")

    def getUserToken(self,user_id):

        try:
            user = self.client.user(user_id)

            user_auth = JWTAuth(
                client_id=os.environ['BOX_CLIENT_ID'],
                client_secret=os.environ['BOX_CLIENT_SECRET'],
                enterprise_id=os.environ['BOX_CLIENT_EID'],
                jwt_key_id=os.environ['BOX_JWT_KEY'],
                rsa_private_key_file_sys_path=os.environ['BOX_PRIVATE_KEY'],
                rsa_private_key_passphrase=os.environ['BOX_PRIVATE_KEY_PASSPHRASE'],
                user=user
            )

            user_auth.authenticate_user()

            self.client = Client(user_auth)
        except Exception as e:
            self.logger.exception(f"Unable to authenticate user {user_id}")

    def get_preview_token(self, file_id):
        self.logger.debug(f"file_id {file_id}")

        target_file = self.client.file(file_id=file_id)
        self.logger.debug(f"target_file {target_file}")
        
        scopes = [
            'base_explorer', 'item_preview', 'item_download', 'item_rename', 'item_share', 'item_delete',
            'base_picker', 'item_upload', 'base_preview', 'annotation_edit', 'annotation_view_all', 
            'annotation_view_self', 'base_sidebar', 'item_comment', 'base_upload'
        ]
        
        token_info = self.client.downscope_token(scopes, target_file)
        self.logger.debug(f'Got downscoped access token: {token_info.access_token}')

        return token_info.access_token

    def get_picker_token(self, folder_id):
        self.logger.debug(f"folder_id {folder_id}")

        target_folder = self.client.folder(folder_id=folder_id)
        self.logger.debug(f"target_folder {target_folder}")

        scopes = [
            'base_explorer', 'item_preview', 'item_download', 'item_rename', 'item_share', 'item_delete',
            'base_picker', 'item_upload', 'base_preview', 'annotation_edit', 'annotation_view_all', 
            'annotation_view_self', 'base_sidebar', 'item_comment', 'base_upload'
        ]

        token_info = self.client.downscope_token(scopes, target_folder)
        self.logger.debug(f'Got downscoped access token: {token_info.access_token}')

        return token_info.access_token