#!/usr/bin/env python3
"""
Скрипт для синхронизации задач из Jira в PostgreSQL
"""

import os
import sys
import requests
from datetime import datetime
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import json
import re

# Загружаем переменные окружения
load_dotenv()


class JiraSync:
    def __init__(self):
        # Jira настройки
        jira_url = os.getenv('JIRA_URL')
        # Убираем trailing slash если есть
        self.jira_url = jira_url.rstrip('/') if jira_url else None
        self.jira_login = os.getenv('JIRA_LOGIN')
        self.jira_password = os.getenv('JIRA_PASSWORD')
        
        # Проверяем наличие всех необходимых переменных
        if not all([self.jira_url, self.jira_login, self.jira_password]):
            print("ОШИБКА: Не все переменные окружения заданы!")
            print(f"JIRA_URL: {'✓' if self.jira_url else '✗'}")
            print(f"JIRA_LOGIN: {'✓' if self.jira_login else '✗'}")
            print(f"JIRA_PASSWORD: {'✓' if self.jira_password else '✗'}")
            sys.exit(1)
        
        # PostgreSQL настройки
        self.pg_config = {
            'host': os.getenv('PGHOST'),
            'user': os.getenv('PGUSER'),
            'password': os.getenv('PGPASSWORD'),
            'database': os.getenv('PGDATABASE'),
            'port': os.getenv('PGPORT', 5432)
        }
        
        self.session = requests.Session()
        self.session.auth = (self.jira_login, self.jira_password)
        self.session.headers.update({'Accept': 'application/json'})
    
    def extract_sprint_name(self, sprint_data: Optional[List]) -> Optional[str]:
        """Извлекает название спринта из массива данных"""
        if not sprint_data or len(sprint_data) == 0:
            return None
        
        # Берем последний спринт (активный)
        sprint_str = sprint_data[-1] if isinstance(sprint_data, list) else sprint_data
        
        # Извлекаем имя спринта из строки формата:
        # com.atlassian.greenhopper.service.sprint.Sprint@...[id=1367,...,name=MAR 08.12.25 - 22.12.25 #24,...]
        match = re.search(r'name=([^,\]]+)', str(sprint_str))
        if match:
            return match.group(1)
        
        return None
    
    def fetch_jira_issues(self, jql: str, start_at: int = 0, max_results: int = 100) -> Dict:
        """Получает задачи из Jira по JQL запросу"""
        url = f"{self.jira_url}/rest/api/2/search"
        
        params = {
            'jql': jql,
            'startAt': start_at,
            'maxResults': max_results,
            'fields': 'key,issuetype,status,created,timeoriginalestimate,timespent,updated,customfield_10104,customfield_10100,summary,assignee,reporter,priority,labels,issuelinks'
        }
        
        print(f"Запрос к: {url}")
        print(f"Параметры: jql='{jql}', startAt={start_at}, maxResults={max_results}")
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            print(f"Ошибка подключения к Jira: {e}")
            print(f"\nПроверьте:")
            print(f"1. Правильность URL: {self.jira_url}")
            print(f"2. Доступность сервера (попробуйте: ping {self.jira_url.replace('https://', '').replace('http://', '')})")
            print(f"3. Подключение к интернету/VPN")
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            print(f"HTTP ошибка: {e}")
            print(f"Код ответа: {response.status_code}")
            print(f"Ответ: {response.text[:500]}")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к Jira API: {e}")
            sys.exit(1)
    
    def fetch_all_issues(self, jql: str) -> List[Dict]:
        """Получает все задачи, обрабатывая пагинацию"""
        all_issues = []
        start_at = 0
        max_results = 100
        
        while True:
            print(f"Получаем задачи с {start_at}...")
            data = self.fetch_jira_issues(jql, start_at, max_results)
            
            issues = data.get('issues', [])
            all_issues.extend(issues)
            
            total = data.get('total', 0)
            print(f"Получено {len(all_issues)} из {total} задач")
            
            if len(all_issues) >= total:
                break
            
            start_at += max_results
        
        return all_issues
    
    def parse_issue(self, issue: Dict) -> Dict:
        """Парсит данные задачи из Jira в формат для БД"""
        fields = issue.get('fields', {})
        
        # Извлекаем связанные задачи
        issue_links = fields.get('issuelinks', [])
        linked_issues_keys = []
        
        for link in issue_links:
            # Может быть inwardIssue или outwardIssue
            if 'inwardIssue' in link:
                linked_issues_keys.append(link['inwardIssue']['key'])
            if 'outwardIssue' in link:
                linked_issues_keys.append(link['outwardIssue']['key'])
        
        # Извлекаем данные
        parsed = {
            'issue_key': issue.get('key'),
            'issue_type': fields.get('issuetype', {}).get('name'),
            'status': fields.get('status', {}).get('name'),
            'created_date': self.parse_date(fields.get('created')),
            'time_original_estimate': self.seconds_to_hours(fields.get('timeoriginalestimate')),
            'time_spent': self.seconds_to_hours(fields.get('timespent')),
            'updated_date': self.parse_date(fields.get('updated')),
            'sprint': self.extract_sprint_name(fields.get('customfield_10104')),
            'epic_link': fields.get('customfield_10100'),
            'summary': fields.get('summary'),
            'assignee': fields.get('assignee', {}).get('displayName') if fields.get('assignee') else None,
            'reporter': fields.get('reporter', {}).get('displayName') if fields.get('reporter') else None,
            'priority': fields.get('priority', {}).get('name'),
            'labels': fields.get('labels', []),
            'linked_issues': linked_issues_keys,
            'issue_links_raw': issue_links  # Сохраняем для детальной таблицы
        }
        
        return parsed
    
    def seconds_to_hours(self, seconds: Optional[int]) -> Optional[float]:
        """Конвертирует секунды в часы с округлением до 2 знаков"""
        if seconds is None:
            return None
        return round(seconds / 3600.0, 2)
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Конвертирует строку даты в datetime объект"""
        if not date_str:
            return None
        
        try:
            # Формат: 2025-12-15T14:34:02.000+0000
            return datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
        except (ValueError, TypeError):
            return None
    
    def get_db_connection(self):
        """Создает подключение к PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.pg_config)
            return conn
        except psycopg2.Error as e:
            print(f"Ошибка подключения к PostgreSQL: {e}")
            sys.exit(1)
    
    def init_database(self):
        """Инициализирует базу данных (создает таблицу если не существует)"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            with open('init_db.sql', 'r', encoding='utf-8') as f:
                sql = f.read()
                cursor.execute(sql)
                conn.commit()
                print("База данных инициализирована успешно")
        except Exception as e:
            print(f"Ошибка при инициализации БД: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    def save_issues_to_db(self, issues: List[Dict]):
        """Сохраняет задачи в PostgreSQL"""
        if not issues:
            print("Нет задач для сохранения")
            return
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # SQL для вставки задач с обновлением при конфликте
        insert_issues_sql = """
        INSERT INTO jira_issues (
            issue_key, issue_type, status, created_date, 
            time_original_estimate, time_spent, updated_date, 
            sprint, epic_link, summary, assignee, reporter, 
            priority, labels, linked_issues, last_synced
        ) VALUES %s
        ON CONFLICT (issue_key) 
        DO UPDATE SET
            issue_type = EXCLUDED.issue_type,
            status = EXCLUDED.status,
            created_date = EXCLUDED.created_date,
            time_original_estimate = EXCLUDED.time_original_estimate,
            time_spent = EXCLUDED.time_spent,
            updated_date = EXCLUDED.updated_date,
            sprint = EXCLUDED.sprint,
            epic_link = EXCLUDED.epic_link,
            summary = EXCLUDED.summary,
            assignee = EXCLUDED.assignee,
            reporter = EXCLUDED.reporter,
            priority = EXCLUDED.priority,
            labels = EXCLUDED.labels,
            linked_issues = EXCLUDED.linked_issues,
            last_synced = CURRENT_TIMESTAMP
        """
        
        # Подготавливаем данные для вставки задач
        issues_values = []
        all_links = []  # Для сохранения связей
        
        for issue in issues:
            parsed = self.parse_issue(issue)
            issues_values.append((
                parsed['issue_key'],
                parsed['issue_type'],
                parsed['status'],
                parsed['created_date'],
                parsed['time_original_estimate'],
                parsed['time_spent'],
                parsed['updated_date'],
                parsed['sprint'],
                parsed['epic_link'],
                parsed['summary'],
                parsed['assignee'],
                parsed['reporter'],
                parsed['priority'],
                parsed['labels'],
                parsed['linked_issues'],
                datetime.now()
            ))
            
            # Собираем связи для детальной таблицы
            source_key = parsed['issue_key']
            for link in parsed['issue_links_raw']:
                link_type = link.get('type', {})
                
                # Обрабатываем inward связи
                if 'inwardIssue' in link:
                    target = link['inwardIssue']
                    all_links.append({
                        'source_key': source_key,
                        'target_key': target['key'],
                        'link_type': link_type.get('id'),
                        'link_type_name': link_type.get('name'),
                        'direction': 'inward',
                        'direction_label': link_type.get('inward'),
                        'target_summary': target.get('fields', {}).get('summary'),
                        'target_status': target.get('fields', {}).get('status', {}).get('name'),
                        'target_priority': target.get('fields', {}).get('priority', {}).get('name')
                    })
                
                # Обрабатываем outward связи
                if 'outwardIssue' in link:
                    target = link['outwardIssue']
                    all_links.append({
                        'source_key': source_key,
                        'target_key': target['key'],
                        'link_type': link_type.get('id'),
                        'link_type_name': link_type.get('name'),
                        'direction': 'outward',
                        'direction_label': link_type.get('outward'),
                        'target_summary': target.get('fields', {}).get('summary'),
                        'target_status': target.get('fields', {}).get('status', {}).get('name'),
                        'target_priority': target.get('fields', {}).get('priority', {}).get('name')
                    })
        
        try:
            # Сохраняем задачи
            execute_values(cursor, insert_issues_sql, issues_values)
            print(f"✓ Сохранено/обновлено {len(issues_values)} задач")
            
            # Удаляем старые связи для обновленных задач
            updated_keys = [parsed['issue_key'] for parsed in [self.parse_issue(i) for i in issues]]
            if updated_keys:
                cursor.execute(
                    "DELETE FROM jira_issue_links WHERE source_issue_key = ANY(%s)",
                    (updated_keys,)
                )
            
            # Сохраняем связи
            if all_links:
                links_sql = """
                INSERT INTO jira_issue_links (
                    source_issue_key, target_issue_key, link_type, link_type_name,
                    direction, direction_label, target_summary, target_status, target_priority
                ) VALUES %s
                """
                
                links_values = [
                    (
                        link['source_key'],
                        link['target_key'],
                        link['link_type'],
                        link['link_type_name'],
                        link['direction'],
                        link['direction_label'],
                        link['target_summary'],
                        link['target_status'],
                        link['target_priority']
                    )
                    for link in all_links
                ]
                
                execute_values(cursor, links_sql, links_values)
                print(f"✓ Сохранено {len(links_values)} связей между задачами")
            
            conn.commit()
            
        except Exception as e:
            print(f"Ошибка при сохранении в БД: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    def sync(self, jql: str):
        """Основной метод синхронизации"""
        print(f"Начинаем синхронизацию с JQL: {jql}")
        print("-" * 60)
        
        # Получаем задачи из Jira
        issues = self.fetch_all_issues(jql)
        
        if not issues:
            print("Задачи не найдены")
            return
        
        # Сохраняем в БД
        self.save_issues_to_db(issues)
        
        print("-" * 60)
        print("Синхронизация завершена")
    
    def get_statistics(self):
        """Выводит статистику из БД"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM jira_issues")
            total = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM jira_issues 
                GROUP BY status 
                ORDER BY COUNT(*) DESC
            """)
            by_status = cursor.fetchall()
            
            cursor.execute("""
                SELECT issue_type, COUNT(*) 
                FROM jira_issues 
                GROUP BY issue_type 
                ORDER BY COUNT(*) DESC
            """)
            by_type = cursor.fetchall()
            
            cursor.execute("SELECT COUNT(*) FROM jira_issue_links")
            total_links = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT link_type_name, direction, COUNT(*) 
                FROM jira_issue_links 
                GROUP BY link_type_name, direction 
                ORDER BY COUNT(*) DESC
            """)
            by_link_type = cursor.fetchall()
            
            print("\n=== Статистика ===")
            print(f"Всего задач в БД: {total}")
            print(f"Всего связей между задачами: {total_links}")
            
            print("\nПо статусам:")
            for status, count in by_status:
                print(f"  {status}: {count}")
            
            print("\nПо типам:")
            for issue_type, count in by_type:
                print(f"  {issue_type}: {count}")
            
            if by_link_type:
                print("\nПо типам связей:")
                for link_type, direction, count in by_link_type:
                    print(f"  {link_type} ({direction}): {count}")
            
        finally:
            cursor.close()
            conn.close()


def main():
    """Главная функция"""
    # Создаем экземпляр синхронизатора
    sync = JiraSync()
    
    # Инициализируем БД (создаем таблицу если не существует)
    sync.init_database()
    
    # JQL запрос (можно изменить на нужный)
    jql = "assignee=currentUser() AND created >= 2025-10-01 AND created <= 2025-12-16"
    
    # Можно также принимать JQL из аргументов командной строки
    if len(sys.argv) > 1:
        jql = sys.argv[1]
    
    # Синхронизируем
    sync.sync(jql)
    
    # Выводим статистику
    sync.get_statistics()


if __name__ == "__main__":
    main()