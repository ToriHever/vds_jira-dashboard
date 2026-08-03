#!/usr/bin/env python3
"""
Клиент для работы с комментариями и вложениями Jira (REST API v2, Jira Server/DC).

Комментарии в Jira - это список независимых объектов, поэтому создание нового
комментария никогда не затрагивает существующие. "Дописывание" в конец уже
существующего комментария не поддерживается Jira напрямую (PUT на комментарий
целиком заменяет body) - поэтому оно эмулируется здесь: тело комментария
считывается, к нему добавляется новый текст, и получившийся результат
отправляется обратно через PUT.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()


class JiraCommentError(Exception):
    pass


class JiraCommentClient:
    def __init__(self):
        jira_url = os.getenv('JIRA_URL')
        self.jira_url = jira_url.rstrip('/') if jira_url else None
        self.jira_login = os.getenv('JIRA_LOGIN')
        self.jira_password = os.getenv('JIRA_PASSWORD')

        if not all([self.jira_url, self.jira_login, self.jira_password]):
            raise JiraCommentError('JIRA_URL/JIRA_LOGIN/JIRA_PASSWORD не заданы в окружении')

        self.session = requests.Session()
        self.session.auth = (self.jira_login, self.jira_password)
        self.session.headers.update({'Accept': 'application/json'})

    def _url(self, path: str) -> str:
        return f"{self.jira_url}{path}"

    def _raise_for_status(self, response):
        if not response.ok:
            raise JiraCommentError(
                f"Jira API вернул {response.status_code}: {response.text[:500]}"
            )

    # --- Комментарии -----------------------------------------------------

    def list_comments(self, issue_key: str) -> list:
        resp = self.session.get(self._url(f"/rest/api/2/issue/{issue_key}/comment"))
        self._raise_for_status(resp)
        return resp.json().get('comments', [])

    def get_comment(self, issue_key: str, comment_id: str) -> dict:
        resp = self.session.get(
            self._url(f"/rest/api/2/issue/{issue_key}/comment/{comment_id}")
        )
        self._raise_for_status(resp)
        return resp.json()

    def append_to_comment(self, issue_key: str, comment_id: str, text: str,
                           separator: str = "\n\n") -> dict:
        """Дописывает text в конец существующего комментария, не трогая уже написанное."""
        current = self.get_comment(issue_key, comment_id)
        current_body = current.get('body') or ''
        new_body = f"{current_body}{separator}{text}" if current_body else text
        resp = self.session.put(
            self._url(f"/rest/api/2/issue/{issue_key}/comment/{comment_id}"),
            json={'body': new_body}
        )
        self._raise_for_status(resp)
        return resp.json()

    def add_comment(self, issue_key: str, text: str) -> dict:
        """Создаёт новый (отдельный) комментарий."""
        resp = self.session.post(
            self._url(f"/rest/api/2/issue/{issue_key}/comment"),
            json={'body': text}
        )
        self._raise_for_status(resp)
        return resp.json()

    # --- Вложения (картинки) ----------------------------------------------

    def upload_attachment(self, issue_key: str, filename: str, file_bytes: bytes,
                           mime_type: str = 'application/octet-stream') -> list:
        """Загружает файл как вложение к задаче. Возвращает метаданные вложений."""
        resp = self.session.post(
            self._url(f"/rest/api/2/issue/{issue_key}/attachments"),
            headers={'X-Atlassian-Token': 'no-check'},
            files={'file': (filename, file_bytes, mime_type)}
        )
        self._raise_for_status(resp)
        return resp.json()

    def append_image_to_comment(self, issue_key: str, comment_id: str,
                                 filename: str, file_bytes: bytes,
                                 mime_type: str = 'application/octet-stream',
                                 text: str = '') -> dict:
        """Загружает картинку как вложение к задаче и дописывает ссылку на неё
        (wiki-markup !filename!) в конец указанного комментария."""
        attachments = self.upload_attachment(issue_key, filename, file_bytes, mime_type)
        uploaded_name = attachments[-1]['filename'] if attachments else filename
        markup = f"!{uploaded_name}!"
        appended = f"{text}\n{markup}" if text else markup
        return self.append_to_comment(issue_key, comment_id, appended)

    def list_attachments(self, issue_key: str) -> list:
        resp = self.session.get(
            self._url(f"/rest/api/2/issue/{issue_key}"),
            params={'fields': 'attachment'}
        )
        self._raise_for_status(resp)
        return resp.json().get('fields', {}).get('attachment', [])

    def get_attachment_meta(self, attachment_id: str) -> dict:
        resp = self.session.get(self._url(f"/rest/api/2/attachment/{attachment_id}"))
        self._raise_for_status(resp)
        return resp.json()

    def get_attachment_content(self, attachment_id: str):
        """Возвращает (bytes, content_type, filename) содержимого вложения."""
        meta = self.get_attachment_meta(attachment_id)
        content_url = meta['content']
        resp = self.session.get(content_url)
        self._raise_for_status(resp)
        return resp.content, meta.get('mimeType', 'application/octet-stream'), meta.get('filename')
