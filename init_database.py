#!/usr/bin/env python3
"""
Скрипт для инициализации/пересоздания таблицы jira_issues
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# SQL для создания таблицы
CREATE_TABLE_SQL = """
-- Удаляем старую таблицу если есть
DROP TABLE IF EXISTS jira_issue_links CASCADE;
DROP TABLE IF EXISTS jira_issues CASCADE;

-- Создаем новую таблицу задач
CREATE TABLE jira_issues (
    id SERIAL PRIMARY KEY,
    issue_key VARCHAR(50) UNIQUE NOT NULL,
    issue_type VARCHAR(100),
    status VARCHAR(100),
    created_date TIMESTAMP,
    time_original_estimate NUMERIC(10, 2),
    time_spent NUMERIC(10, 2),
    updated_date TIMESTAMP,
    sprint VARCHAR(500),
    epic_link VARCHAR(50),
    summary TEXT,
    assignee VARCHAR(255),
    reporter VARCHAR(255),
    priority VARCHAR(50),
    labels TEXT[],
    linked_issues TEXT[],
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создаем таблицу связей
CREATE TABLE jira_issue_links (
    id SERIAL PRIMARY KEY,
    source_issue_key VARCHAR(50) NOT NULL,
    target_issue_key VARCHAR(50) NOT NULL,
    link_type VARCHAR(100),
    link_type_name VARCHAR(200),
    direction VARCHAR(20),
    direction_label VARCHAR(100),
    target_summary TEXT,
    target_status VARCHAR(100),
    target_priority VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_issue_key) REFERENCES jira_issues(issue_key) ON DELETE CASCADE
);

-- Создаем индексы для задач
CREATE INDEX idx_issue_key ON jira_issues(issue_key);
CREATE INDEX idx_created_date ON jira_issues(created_date);
CREATE INDEX idx_status ON jira_issues(status);
CREATE INDEX idx_assignee ON jira_issues(assignee);
CREATE INDEX idx_sprint ON jira_issues(sprint);
CREATE INDEX idx_epic_link ON jira_issues(epic_link);

-- Создаем индексы для связей
CREATE INDEX idx_source_issue ON jira_issue_links(source_issue_key);
CREATE INDEX idx_target_issue ON jira_issue_links(target_issue_key);
CREATE INDEX idx_link_type ON jira_issue_links(link_type);
CREATE INDEX idx_both_issues ON jira_issue_links(source_issue_key, target_issue_key);

-- Комментарии
COMMENT ON TABLE jira_issues IS 'Таблица для хранения задач из Jira';
COMMENT ON COLUMN jira_issues.time_original_estimate IS 'Первоначальная оценка в часах';
COMMENT ON COLUMN jira_issues.time_spent IS 'Затраченное время в часах';
COMMENT ON COLUMN jira_issues.linked_issues IS 'Массив ключей связанных задач';

COMMENT ON TABLE jira_issue_links IS 'Детальная информация о связях между задачами для построения карты';
COMMENT ON COLUMN jira_issue_links.direction IS 'Направление связи: inward или outward';
"""

def main():
    # Настройки подключения
    conn_params = {
        'host': os.getenv('PGHOST'),
        'user': os.getenv('PGUSER'),
        'password': os.getenv('PGPASSWORD'),
        'database': os.getenv('PGDATABASE'),
        'port': os.getenv('PGPORT', 5432)
    }
    
    print("Подключение к PostgreSQL...")
    print(f"Host: {conn_params['host']}")
    print(f"Database: {conn_params['database']}")
    print(f"User: {conn_params['user']}")
    print()
    
    try:
        # Подключаемся
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        print("Удаление старой таблицы и создание новой...")
        
        # Выполняем SQL
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        
        print("✓ Таблица jira_issues успешно создана!")
        print()
        
        # Проверяем структуру
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'jira_issues'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        print("Структура таблицы:")
        print("-" * 70)
        print(f"{'Колонка':<30} {'Тип':<20} {'Длина':<10}")
        print("-" * 70)
        
        for col_name, data_type, max_length in columns:
            length_str = str(max_length) if max_length else '-'
            print(f"{col_name:<30} {data_type:<20} {length_str:<10}")
        
        print("-" * 70)
        print(f"Всего колонок: {len(columns)}")
        
        cursor.close()
        conn.close()
        
        print()
        print("База данных готова к использованию!")
        print("Теперь можно запустить: python jira_sync.py")
        
    except psycopg2.Error as e:
        print(f"Ошибка PostgreSQL: {e}")
        return 1
    except Exception as e:
        print(f"Ошибка: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())