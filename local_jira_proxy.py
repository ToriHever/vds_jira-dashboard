#!/usr/bin/env python3
"""
Локальный прокси-сервис для работы с комментариями/вложениями Jira.

Зачем: основной дашборд (app.py) крутится на VDS, у которого нет сетевого
доступа до Jira. Но браузер, в котором вы открываете дашборд, работает на
вашем компьютере - а у него доступ к Jira есть. Поэтому JS дашборда ходит
за операциями с комментариями не на VDS, а сюда, на localhost - запускайте
этот скрипт на своей машине рядом с браузером.

Запуск:
    python local_jira_proxy.py

Требует в .env (локально, рядом с этим файлом): JIRA_URL, JIRA_LOGIN,
JIRA_PASSWORD - те же, что использует jira_sync.py.
"""

import os
import sys
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from dotenv import load_dotenv
from jira_comments import JiraCommentClient, JiraCommentError

# Консоль Windows по умолчанию использует cp1251/cp866, которая не умеет
# печатать часть символов (например эмодзи) - переключаем на UTF-8, чтобы
# любой вывод (в том числе от Flask/Werkzeug) не валил процесс.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

app = Flask(__name__)
# Сервис слушает только localhost, поэтому дотянуться до него может только
# браузер на этой же машине - ограничивать источники CORS нет смысла.
CORS(app)

PORT = int(os.getenv('JIRA_PROXY_PORT', 5057))


@app.after_request
def allow_private_network(response):
    # Если дашборд открыт по HTTPS с VDS, а прокси - http://localhost,
    # Chrome требует этот заголовок для запросов "публичный сайт -> локальная сеть".
    response.headers['Access-Control-Allow-Private-Network'] = 'true'
    return response


@app.route('/api/issue/<issue_key>/comments')
def get_issue_comments(issue_key):
    try:
        client = JiraCommentClient()
        comments = client.list_comments(issue_key)
        attachments = client.list_attachments(issue_key)
        return jsonify({'comments': comments, 'attachments': attachments})
    except JiraCommentError as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/issue/<issue_key>/comment', methods=['POST'])
def add_issue_comment(issue_key):
    body = request.get_json() or {}
    text = body.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Пустой текст комментария'}), 400
    try:
        client = JiraCommentClient()
        comment = client.add_comment(issue_key, text)
        return jsonify(comment)
    except JiraCommentError as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/issue/<issue_key>/comment/<comment_id>/append', methods=['POST'])
def append_issue_comment(issue_key, comment_id):
    body = request.get_json() or {}
    text = body.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Пустой текст для дописывания'}), 400
    try:
        client = JiraCommentClient()
        comment = client.append_to_comment(issue_key, comment_id, text)
        return jsonify(comment)
    except JiraCommentError as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/issue/<issue_key>/comment/<comment_id>/append-image', methods=['POST'])
def append_issue_comment_image(issue_key, comment_id):
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({'error': 'Файл не передан'}), 400
    caption = request.form.get('text', '').strip()
    try:
        client = JiraCommentClient()
        comment = client.append_image_to_comment(
            issue_key, comment_id,
            filename=file.filename,
            file_bytes=file.read(),
            mime_type=file.mimetype or 'application/octet-stream',
            text=caption
        )
        return jsonify(comment)
    except JiraCommentError as e:
        return jsonify({'error': str(e)}), 502


@app.route('/api/attachment/<attachment_id>/content')
def get_attachment_content(attachment_id):
    try:
        client = JiraCommentClient()
        content, mime_type, filename = client.get_attachment_content(attachment_id)
        return Response(content, mimetype=mime_type, headers={
            'Content-Disposition': f'inline; filename="{filename}"'
        })
    except JiraCommentError as e:
        return jsonify({'error': str(e)}), 502


if __name__ == '__main__':
    print(f"Локальный Jira-прокси запущен: http://localhost:{PORT}")
    print("Держите этот терминал открытым, пока пользуетесь комментариями в дашборде.")
    app.run(host='127.0.0.1', port=PORT, debug=False)
