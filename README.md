# Tennis Tournament Telegram Bot

Telegram-бот для регистрации игроков, ввода результатов и таблицы турнира.
Для постоянной работы используйте внешний PostgreSQL и worker с long polling.

## Локальная проверка

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# заполните .env
python migrate.py
python -m unittest discover -s tests
python bot.py
```

В `.env` обязательны:

```env
BOT_TOKEN=токен_от_BotFather
DATABASE_URL=
ALLOWED_JUDGES=123456789,987654321
```

`ALLOWED_JUDGES` обязателен для ввода результатов и запуска турнира.

## Команды

- `/start` — открыть меню
- `/register_player Имя` — зарегистрировать игрока
- `/players` — список игроков
- `/start_tournament` — начать турнир
- `/finish_tournament` — завершить турнир и запретить новые результаты
- `/delete_all_players CONFIRM` — удалить всех участников, матчи и статистику
- `/result "Имя Победителя" "Имя Проигравшего" 6:3 7:5` — добавить результат
- `/table` — турнирная таблица
- `/stats` — статистика
- `/cancel` — отменить ввод

Счет принимает сеты формата `6:0`–`6:4`, `7:5`, `7:6`; победитель должен выиграть большинство указанных сетов.

## Онлайн бесплатно

1. Создайте бота через `@BotFather` и скопируйте токен.
2. Создайте PostgreSQL-базу на Neon или Supabase. Скопируйте строку подключения `DATABASE_URL`.
3. Загрузите проект в приватный GitHub-репозиторий. Не добавляйте `.env` и `*.db`.
4. Создайте worker на хостинге, который поддерживает постоянный бесплатный процесс, например Oracle Cloud Always Free VM.
5. На VM установите Git и Python, клонируйте репозиторий и выполните:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
printf 'BOT_TOKEN=...\nDATABASE_URL=...\nALLOWED_JUDGES=...\n' > .env
python migrate.py
```

6. Запустите процесс:

```bash
nohup .venv/bin/python bot.py > bot.log 2>&1 &
```

Для автоматического перезапуска используйте systemd или supervisor:

```ini
[Service]
WorkingDirectory=/opt/tennis-bot
ExecStart=/opt/tennis-bot/.venv/bin/python bot.py
Restart=always
EnvironmentFile=/opt/tennis-bot/.env
```

Oracle Cloud и бесплатные базы имеют ограничения, а бесплатные планы могут измениться. SQLite годится только для локальной проверки: на эфемерном хостинге данные могут исчезнуть.
