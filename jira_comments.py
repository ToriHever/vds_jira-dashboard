#!/usr/bin/env python3
"""
Клиент для работы с комментариями и вложениями Jira (REST API v2, Jira Server/DC).

Комментарии в Jira - это список независимых объектов, поэтому создание нового
комментария никогда не затрагивает существующие. Полное редактирование
существующего комментария (update_comment) заменяет body целиком - это
делается по явному действию пользователя в UI (кнопка "сохранить"), а не
случайно.
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

    def _request(self, method: str, url: str, **kwargs):
        try:
            return self.session.request(method, url, timeout=15, **kwargs)
        except requests.exceptions.RequestException as e:
            raise JiraCommentError(f"Не удалось подключиться к Jira: {e}") from e

    def _raise_for_status(self, response):
        if not response.ok:
            raise JiraCommentError(
                f"Jira API вернул {response.status_code}: {response.text[:500]}"
            )

    # --- Комментарии -----------------------------------------------------

    def list_comments(self, issue_key: str) -> list:
        resp = self._request('GET', self._url(f"/rest/api/2/issue/{issue_key}/comment"))
        self._raise_for_status(resp)
        return resp.json().get('comments', [])

    def get_comment(self, issue_key: str, comment_id: str) -> dict:
        resp = self._request(
            'GET', self._url(f"/rest/api/2/issue/{issue_key}/comment/{comment_id}")
        )
        self._raise_for_status(resp)
        return resp.json()

    def update_comment(self, issue_key: str, comment_id: str, body: str) -> dict:
        """Полностью заменяет текст существующего комментария (редактирование)."""
        resp = self._request(
            'PUT', self._url(f"/rest/api/2/issue/{issue_key}/comment/{comment_id}"),
            json={'body': body}
        )
        self._raise_for_status(resp)
        return resp.json()

    def add_comment(self, issue_key: str, text: str) -> dict:
        """Создаёт новый (отдельный) комментарий."""
        resp = self._request(
            'POST', self._url(f"/rest/api/2/issue/{issue_key}/comment"),
            json={'body': text}
        )
        self._raise_for_status(resp)
        return resp.json()

    # --- Вложения (картинки) ----------------------------------------------

    def upload_attachment(self, issue_key: str, filename: str, file_bytes: bytes,
                           mime_type: str = 'application/octet-stream') -> list:
        """Загружает файл как вложение к задаче. Возвращает метаданные вложений."""
        resp = self._request(
            'POST', self._url(f"/rest/api/2/issue/{issue_key}/attachments"),
            headers={'X-Atlassian-Token': 'no-check'},
            files={'file': (filename, file_bytes, mime_type)}
        )
        self._raise_for_status(resp)
        return resp.json()

    def list_attachments(self, issue_key: str) -> list:
        resp = self._request(
            'GET', self._url(f"/rest/api/2/issue/{issue_key}"),
            params={'fields': 'attachment'}
        )
        self._raise_for_status(resp)
        return resp.json().get('fields', {}).get('attachment', [])

    def get_attachment_meta(self, attachment_id: str) -> dict:
        resp = self._request('GET', self._url(f"/rest/api/2/attachment/{attachment_id}"))
        self._raise_for_status(resp)
        return resp.json()

    def get_attachment_content(self, attachment_id: str):
        """Возвращает (bytes, content_type, filename) содержимого вложения."""
        meta = self.get_attachment_meta(attachment_id)
        content_url = meta['content']
        resp = self._request('GET', content_url)
        self._raise_for_status(resp)
        return resp.content, meta.get('mimeType', 'application/octet-stream'), meta.get('filename')
