#!/usr/bin/env python3
"""
Flask веб-приложение для отображения задач Jira из PostgreSQL
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

# Конфигурация БД
DB_CONFIG = {
    'host': os.getenv('PGHOST'),
    'user': os.getenv('PGUSER'),
    'password': os.getenv('PGPASSWORD'),
    'database': os.getenv('PGDATABASE'),
    'port': os.getenv('PGPORT', 5432)
}


def get_db_connection():
    """Создает подключение к PostgreSQL"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def format_date(date_obj):
    """Форматирует дату для отображения"""
    if date_obj:
        return date_obj.strftime('%d.%m.%Y %H:%M')
    return '-'


def format_hours(hours):
    """Форматирует часы для отображения"""
    if hours:
        return f"{hours:.2f}ч"
    return '-'


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html', v=datetime.now().timestamp())


@app.route('/api/issues')
def get_issues():
    """API: Получить все задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            issue_key,
            issue_type,
            status,
            summary,
            assignee,
            priority,
            created_date,
            updated_date,
            time_original_estimate,
            time_spent,
            sprint,
            epic_link,
            labels,
            linked_issues,
            last_synced
        FROM jira_issues
        ORDER BY updated_date DESC
    """)
    
    issues = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Конвертируем даты в строки для JSON
    for issue in issues:
        issue['created_date'] = format_date(issue['created_date'])
        issue['updated_date'] = format_date(issue['updated_date'])
        issue['last_synced'] = format_date(issue['last_synced'])
    
    return jsonify(issues)


@app.route('/api/statistics')
def get_statistics():
    """API: Получить статистику"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) as total FROM jira_issues")
    total = cursor.fetchone()['total']
    
    # По статусам
    cursor.execute("""
        SELECT status, COUNT(*) as count 
        FROM jira_issues 
        GROUP BY status 
        ORDER BY count DESC
    """)
    by_status = cursor.fetchall()
    
    # По типам
    cursor.execute("""
        SELECT issue_type, COUNT(*) as count 
        FROM jira_issues 
        GROUP BY issue_type 
        ORDER BY count DESC
    """)
    by_type = cursor.fetchall()
    
    # По спринтам
    cursor.execute("""
        SELECT 
            sprint,
            COUNT(*) as count,
            ROUND(SUM(time_original_estimate), 2) as total_estimate,
            ROUND(SUM(time_spent), 2) as total_spent
        FROM jira_issues
        WHERE sprint IS NOT NULL
        GROUP BY sprint
        ORDER BY sprint DESC
        LIMIT 10
    """)
    by_sprint = cursor.fetchall()
    
    # Связи
    cursor.execute("SELECT COUNT(*) as total FROM jira_issue_links")
    total_links = cursor.fetchone()['total']
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'total': total,
        'total_links': total_links,
        'by_status': by_status,
        'by_type': by_type,
        'by_sprint': by_sprint
    })


@app.route('/api/current-sprint-stats')
def get_current_sprint_stats():
    """Статистика по текущему спринту"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Находим текущий спринт (с максимальным номером)
    cursor.execute("""
        SELECT 
            stats.*
        FROM (
            SELECT 
                sprint,
                COUNT(*) as total_tasks,
                COUNT(CASE WHEN status = 'Готово' THEN 1 END) as completed_tasks,
                COUNT(CASE WHEN status = 'В работе' THEN 1 END) as in_progress_tasks,
                COUNT(CASE WHEN status = 'Открыто' THEN 1 END) as open_tasks,
                COALESCE(SUM(time_original_estimate), 0) as total_estimated,
                COALESCE(SUM(time_spent), 0) as total_spent,
                COALESCE(SUM(CASE WHEN status = 'Готово' THEN time_spent ELSE 0 END), 0) as completed_spent
            FROM jira_issues
            WHERE sprint IS NOT NULL
            GROUP BY sprint
        ) as stats
        WHERE stats.sprint = (
            SELECT sprint
            FROM jira_issues
            WHERE sprint IS NOT NULL
            GROUP BY sprint
            -- ИСПРАВЛЕНИЕ: INSTR → STRPOS
            ORDER BY CAST(SUBSTR(sprint, STRPOS(sprint, '#') + 1) AS INTEGER) DESC
            LIMIT 1)
    """)
    
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not result:
        return jsonify({
            'error': 'Нет данных по спринтам',
            'sprint_name': None
        })
    
    # Константы
    SPRINT_CAPACITY = 80  # часов на спринт (2 недели)
    
    # Расчёты
    total_estimated = float(result['total_estimated'])
    total_spent = float(result['total_spent'])
    completed_spent = float(result['completed_spent'])
    
    # Прогресс по задачам
    progress_percent = (result['completed_tasks'] / result['total_tasks'] * 100) if result['total_tasks'] > 0 else 0
    
    # Загруженность спринта
    workload_percent = (total_estimated / SPRINT_CAPACITY * 100)
    
    # Использовано времени от capacity
    time_used_percent = (total_spent / SPRINT_CAPACITY * 100)
    
    # Оставшееся время
    remaining_capacity = SPRINT_CAPACITY - total_spent
    remaining_work = total_estimated - completed_spent
    
    # Статус загруженности
    if workload_percent > 100:
        workload_status = 'overloaded'
    elif workload_percent > 90:
        workload_status = 'full'
    elif workload_percent > 70:
        workload_status = 'normal'
    else:
        workload_status = 'light'
    
    return jsonify({
        'sprint_name': result['sprint'],
        'sprint_capacity': SPRINT_CAPACITY,
        'total_tasks': result['total_tasks'],
        'completed_tasks': result['completed_tasks'],
        'in_progress_tasks': result['in_progress_tasks'],
        'open_tasks': result['open_tasks'],
        'total_estimated': round(total_estimated, 2),
        'total_spent': round(total_spent, 2),
        'completed_spent': round(completed_spent, 2),
        'remaining_capacity': round(remaining_capacity, 2),
        'remaining_work': round(remaining_work, 2),
        'progress_percent': round(progress_percent, 1),
        'workload_percent': round(workload_percent, 1),
        'time_used_percent': round(time_used_percent, 1),
        'workload_status': workload_status
    })


@app.route('/api/issue/<issue_key>')
def get_issue_details(issue_key):
    """API: Получить детали задачи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Основная информация
    cursor.execute("""
        SELECT * FROM jira_issues WHERE issue_key = %s
    """, (issue_key,))
    issue = cursor.fetchone()
    
    if not issue:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Issue not found'}), 404
    
    # Связи
    cursor.execute("""
        SELECT 
            target_issue_key,
            link_type_name,
            direction,
            direction_label,
            target_summary,
            target_status,
            target_priority
        FROM jira_issue_links
        WHERE source_issue_key = %s
    """, (issue_key,))
    links = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Форматируем даты
    issue['created_date'] = format_date(issue['created_date'])
    issue['updated_date'] = format_date(issue['updated_date'])
    issue['last_synced'] = format_date(issue['last_synced'])
    
    return jsonify({
        'issue': issue,
        'links': links
    })


@app.route('/api/graph')
def get_graph_data():
    """API: Получить данные для графа связей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем все задачи, которые имеют связи
    cursor.execute("""
        SELECT DISTINCT issue_key, summary, status, issue_type, priority
        FROM jira_issues
        WHERE issue_key IN (
            SELECT DISTINCT source_issue_key FROM jira_issue_links
            UNION
            SELECT DISTINCT target_issue_key FROM jira_issue_links
        )
    """)
    nodes = cursor.fetchall()
    
    # Получаем все связи
    cursor.execute("""
        SELECT 
            source_issue_key,
            target_issue_key,
            link_type_name,
            direction_label,
            direction
        FROM jira_issue_links
    """)
    edges = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'nodes': nodes,
        'edges': edges
    })


@app.template_filter('format_date')
def format_date_filter(date_obj):
    return format_date(date_obj)


@app.template_filter('format_hours')
def format_hours_filter(hours):
    return format_hours(hours)


if __name__ == '__main__':
    print("🚀 Запуск веб-приложения Jira Dashboard...")
    print("📊 Доступно по адресу: http://localhost:5000")
    print("🔄 Обновите данные с помощью: python jira_sync.py")
    print("-" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)