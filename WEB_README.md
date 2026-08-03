# Jira Web Dashboard

Веб-приложение для визуализации задач из Jira, хранящихся в PostgreSQL.

## 🎯 Возможности

✅ **Автоматическое обновление** - данные загружаются из БД в реальном времени
✅ **Живая статистика** - количество задач, связей, статусы
✅ **Множество вкладок**:
   - 📋 Все задачи
   - 🏃 По спринтам
   - 📈 По статусам
   - 🔗 Связи между задачами
✅ **Поиск** - быстрый поиск по ключу, описанию, исполнителю
✅ **Автообновление** - каждые 5 минут автоматически обновляет данные
✅ **Красивый дизайн** - современный градиентный интерфейс

## 📦 Установка

```bash
# 1. Установите зависимости
pip install -r requirements_web.txt

# 2. Убедитесь, что .env файл настроен правильно
# (те же настройки, что и для jira_sync.py)
```

## 🚀 Запуск

```bash
# Запустите веб-сервер
python app.py
```

Приложение будет доступно по адресу: **http://localhost:5000**

## 💬 Комментарии Jira (дописывание текста и картинок)

VDS, на котором обычно крутится дашборд, не имеет сетевого доступа к
`jira.ddos-guard.net`. Поэтому работа с комментариями/вложениями Jira
вынесена в отдельный локальный сервис `local_jira_proxy.py`, который
запускается у вас на компьютере (у него доступ к Jira есть) - фронтенд
дашборда (открытый в браузере) ходит за операциями с комментариями именно
туда, на `http://localhost:5057`, а не на VDS.

```bash
# На своём компьютере, рядом с .env (JIRA_URL/JIRA_LOGIN/JIRA_PASSWORD)
# Обратите внимание: requirements_local_proxy.txt, а не requirements_web.txt -
# прокси не трогает Postgres, поэтому psycopg2-binary (которая часто не
# собирается на новых версиях Python без Visual C++ Build Tools) ему не нужна.
pip install -r requirements_local_proxy.txt
python local_jira_proxy.py
```

Держите этот терминал открытым, пока пользуетесь кнопкой "💬 Открыть" в
таблице задач дашборда. Порт можно сменить переменной окружения
`JIRA_PROXY_PORT` (не забудьте поменять `JIRA_PROXY_BASE` в
`static/js/app.js`, если меняете порт).

## 📁 Структура проекта

```
.
├── app.py                  # Flask бэкенд
├── templates/
│   └── index.html         # Главная страница (фронтенд)
├── requirements_web.txt   # Зависимости для веб-приложения
├── .env                   # Конфигурация (БД + Jira)
└── WEB_README.md         # Эта инструкция
```

## 🔄 Рабочий процесс

1. **Синхронизация данных из Jira**:
   ```bash
   python jira_sync.py
   ```

2. **Запуск веб-приложения**:
   ```bash
   python app.py
   ```

3. **Открытие в браузере**:
   - Перейдите на http://localhost:5000
   - Данные загрузятся автоматически
   - Нажмите "🔄 Обновить данные" для принудительного обновления

## 🌐 API Endpoints

Веб-приложение предоставляет REST API для работы с данными:

### GET `/api/issues`
Получить все задачи из БД

**Ответ:**
```json
[
  {
    "issue_key": "PRMR-6929",
    "issue_type": "Задача",
    "status": "В работе",
    "summary": "Контент план для Дзена",
    "assignee": "Victoria Miroshnikova",
    "priority": "Medium",
    "created_date": "15.12.2025 14:34",
    "time_original_estimate": 5.0,
    "time_spent": 0,
    "sprint": "MAR 08.12.25 - 22.12.25 #24",
    "linked_issues": ["PRMR-6924"]
  }
]
```

### GET `/api/statistics`
Получить статистику по задачам

**Ответ:**
```json
{
  "total": 57,
  "total_links": 12,
  "by_status": [
    {"status": "Готово", "count": 31},
    {"status": "Закрыта", "count": 23}
  ],
  "by_type": [...],
  "by_sprint": [...]
}
```

### GET `/api/issue/<issue_key>`
Получить детали конкретной задачи

**Пример:** `/api/issue/PRMR-6929`

**Ответ:**
```json
{
  "issue": {...},
  "links": [
    {
      "target_issue_key": "PRMR-6924",
      "link_type_name": "Проблема, разделенная",
      "direction": "inward",
      "direction_label": "разделить от",
      "target_summary": "Дзен Блог - 2026",
      "target_status": "В работе"
    }
  ]
}
```

### GET `/api/graph`
Получить данные для построения графа связей

**Ответ:**
```json
{
  "nodes": [
    {
      "issue_key": "PRMR-6929",
      "summary": "Контент план",
      "status": "В работе",
      "issue_type": "Задача"
    }
  ],
  "edges": [
    {
      "source_issue_key": "PRMR-6929",
      "target_issue_key": "PRMR-6924",
      "link_type_name": "Проблема, разделенная",
      "direction_label": "разделить от"
    }
  ]
}
```

## 🎨 Интерфейс

### Главная страница
- **Статистические карточки** - общее количество задач, связей, статусы
- **Вкладки** - переключение между разными представлениями
- **Поиск** - фильтрация задач в реальном времени
- **Таблицы** - удобное отображение данных с цветовой кодировкой

### Цветовая кодировка

**Статусы:**
- 🟡 Открыта / New - желтый
- 🔵 В работе / In Progress - голубой
- 🟢 Готово / Done - зеленый
- ⚪ Закрыта / Closed - серый

**Приоритеты:**
- 🔴 High / Высокий - красный
- 🟡 Medium / Средний - желтый
- 🟢 Low / Низкий - зеленый

## 🔧 Настройка

### Изменение порта
По умолчанию приложение запускается на порту 5000. Чтобы изменить:

```python
# В файле app.py, последняя строка:
app.run(debug=True, host='0.0.0.0', port=8080)  # Измените 5000 на 8080
```

### Отключение автообновления
Чтобы отключить автоматическое обновление каждые 5 минут, удалите в `index.html`:

```javascript
// Удалите эту строку:
setInterval(loadData, 5 * 60 * 1000);
```

### Доступ из внешней сети
По умолчанию приложение доступно только с localhost. Чтобы открыть доступ:

```python
# В app.py уже настроено:
app.run(debug=True, host='0.0.0.0', port=5000)
# host='0.0.0.0' означает доступ со всех интерфейсов
```

Затем откройте порт в файрволе:
```bash
# Ubuntu/Debian
sudo ufw allow 5000

# CentOS/RHEL
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

## 🐛 Устранение неполадок

### Ошибка: "Connection refused"
Проверьте, что:
1. Flask приложение запущено (`python app.py`)
2. Порт 5000 не занят другим приложением
3. Файрволл не блокирует подключение

### Ошибка: "No data displayed"
Проверьте:
1. База данных доступна (настройки в `.env`)
2. В БД есть данные (запустите `python jira_sync.py`)
3. Консоль браузера (F12) на наличие ошибок JavaScript

### Ошибка: "Cannot connect to database"
Проверьте настройки в `.env`:
```env
PGHOST=193.176.83.195
PGUSER=tori_db
PGPASSWORD=your_password
PGDATABASE=mar_db
PGPORT=5432
```

## 🚀 Запуск в продакшене

### С помощью Gunicorn (рекомендуется)

```bash
# Установите Gunicorn
pip install gunicorn

# Запустите приложение
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### С помощью systemd (автозапуск)

Создайте файл `/etc/systemd/system/jira-dashboard.service`:

```ini
[Unit]
Description=Jira Dashboard Web Application
After=network.target

[Service]
Type=notify
User=your_user
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
```

Активируйте:
```bash
sudo systemctl daemon-reload
sudo systemctl enable jira-dashboard
sudo systemctl start jira-dashboard
```

### С Nginx (reverse proxy)

Конфигурация Nginx:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Следующие шаги

После запуска веб-приложения вы можете:

1. **Интегрировать с CI/CD** - автоматически синхронизировать данные
2. **Добавить аутентификацию** - защитить доступ к дашборду
3. **Создать графы связей** - визуализировать зависимости задач
4. **Экспортировать отчеты** - генерировать PDF/Excel отчеты
5. **Настроить уведомления** - получать алерты о критичных задачах

## 💡 Полезные команды

```bash
# Синхронизация + запуск веб-приложения
python jira_sync.py && python app.py

# Проверка статуса
curl http://localhost:5000/api/statistics

# Просмотр логов (если запущено через systemd)
sudo journalctl -u jira-dashboard -f
```

## 🎉 Готово!

Ваше веб-приложение готово к использованию. Теперь каждый раз, когда вы запускаете `python jira_sync.py`, данные будут автоматически обновляться на веб-странице.