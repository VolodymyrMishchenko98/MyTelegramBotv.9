# MyTelegramBot 🏋️

Умный Telegram бот для отслеживания физических тренировок, управления профилем и магазина награды с монетной системой.

## 🚀 Возможности

- 📊 **Отслеживание тренировок** - логирование упражнений и их результатов
- 👤 **Профиль пользователя** - информация о росте, весе, возрасте и целях
- 🎯 **Ежедневные задачи** - система ежедневных тренировочных целей
- 🛒 **Магазин** - покупка премиум тренировок и бонусов за монеты
- 💪 **Мотивация** - мотивационные цитаты и вызовы
- 🌍 **Двуязычность** - украинский и английский языки
- 💾 **Стабильная база данных** - оптимизированная SQLite с WAL режимом

## 📋 Требования

- Python 3.8+
- SQLite3 (включен в Python)

## 🔧 Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/yourusername/MyTelegramBot.git
cd MyTelegramBot
```

### 2. Создать виртуальное окружение

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env и добавить свои значения
```

### 5. Получить необходимые ключи

#### 🤖 Telegram Bot Token

1. Откройте Telegram и найдите [@BotFather](https://t.me/botfather)
2. Напишите `/newbot` и следуйте инструкциям
3. Скопируйте полученный токен в `.env`

#### 🔑 API Ninjas Key (для информации о калориях)

1. Перейдите на [api.api-ninjas.com](https://api.api-ninjas.com/)
2. Создайте аккаунт и получите API ключ
3. Добавьте ключ в `.env`

### 6. Запустить бота

```bash
python bot.py
```

## 📁 Структура проекта

```
MyTelegramBot/
├── bot.py                 # Основной файл бота с обработчиками команд
├── db.py                  # Инициализация базы данных
├── db_improved.py         # Оптимизированный модуль работы с БД
├── requirements.txt       # Зависимости Python
├── .env.example          # Пример конфигурации
├── Procfile              # Конфигурация для Heroku
├── SETUP_GUIDE.txt       # Расширенная инструкция по установке
├── LOGIC_ANALYSIS.txt    # Анализ бизнес-логики
├── PURCHASE_LOGIC.txt    # Логика системы покупок
└── README.md             # Этот файл
```

## 🎮 Команди / Commands

Мова бота перемикається командою `/change_language`. Українська та англійська — єдині доступні мови інтерфейсу.

Use `/change_language` to switch the bot between Ukrainian and English; these are the only supported interface languages.

### Українська

| Команда | Призначення |
| --- | --- |
| `/start` | Почати роботу й відкрити меню |
| `/help` | Переглянути список команд і довідку |
| `/developer` | Переглянути картку й зв’язатися з розробником |
| `/change_language` | Перемкнути українську й англійську |
| `/workout` | Записати тренування |
| `/today` | Переглянути активність за сьогодні |
| `/history` | Переглянути історію тренувань |
| `/stats` | Переглянути статистику тренувань |
| `/weight` | Записати вагу тіла |
| `/weight_stats` | Переглянути останні записи ваги |
| `/level` | Переглянути рівень і XP |
| `/chart` | Переглянути графіки прогресу |
| `/profile` | Переглянути профіль |
| `/edit_profile` | Змінити профіль |
| `/profile_visibility` | Налаштувати видимість полів профілю |
| `/set_goal` | Задати тижневу ціль |
| `/goal` | Переглянути тижневу ціль |
| `/suggest` | Запропонувати тренування; потрібна мета в профілі |
| `/daily` | Переглянути щоденне завдання |
| `/challenge` | Переглянути челендж дня |
| `/reminders` | Налаштувати нагадування |
| `/motivate` | Отримати мотиваційне повідомлення |
| `/tip` | Отримати пораду дня |
| `/wallet` | Переглянути монети й інвентар |
| `/shop` | Відкрити магазин предметів |
| `/use` | Використати предмет з інвентарю |
| `/export` | Завантажити копію даних |
| `/import` | Імпортувати JSON; поточні дані буде замінено |
| `/reset` | Видалити дані профілю після підтвердження |
| `/admin` | Статистика бота; лише для ID з `ADMIN_IDS` |
| `/backup` | Створити резервну копію; лише для ID з `ADMIN_IDS` |

### English

| Command | Purpose |
| --- | --- |
| `/start` | Start using the bot and open the menu |
| `/help` | View the command list and quick guide |
| `/developer` | View developer details and get in touch |
| `/change_language` | Switch between Ukrainian and English |
| `/workout` | Record a workout |
| `/today` | View today's activity |
| `/history` | View workout history |
| `/stats` | View workout statistics |
| `/weight` | Record body weight |
| `/weight_stats` | View recent weight entries |
| `/level` | View your level and XP |
| `/chart` | View progress charts |
| `/profile` | View your profile |
| `/edit_profile` | Edit your profile |
| `/profile_visibility` | Manage visible profile fields |
| `/set_goal` | Set a weekly goal |
| `/goal` | View your weekly goal |
| `/suggest` | Suggest a workout; requires a profile goal |
| `/daily` | View the daily task |
| `/challenge` | View the daily challenge |
| `/reminders` | Manage reminders |
| `/motivate` | Get a motivational message |
| `/tip` | Get the tip of the day |
| `/wallet` | View coins and inventory |
| `/shop` | Open the item shop |
| `/use` | Use an inventory item |
| `/export` | Download a copy of your data |
| `/import` | Import JSON; replaces current data |
| `/reset` | Delete profile data after confirmation |
| `/admin` | Bot statistics; only for IDs in `ADMIN_IDS` |
| `/backup` | Create a database backup; only for IDs in `ADMIN_IDS` |

## 🗄️ База данных

Бот использует SQLite с оптимизированной конфигурацией:

- **WAL режим** - для параллельных операций
- **Глобальное соединение** - избегает race conditions
- **Потокобезопасность** - работает с asyncio
- **Автоматические транзакции** - атомарность операций

## � Управление видимостью профиля

Команда `/profile_visibility` позволяет пользователям контролировать, какие данные отображаются в их профиле:

### Доступные поля

- 📏 **Зріст** - рост пользователя
- 🧍 **Стать** - пол пользователя
- 🎂 **Вік** - возраст пользователя
- ⚖️ **Вага** - текущий вес
- 🎯 **Мета** - фитнес-цель

### Как использовать

1. **Открыть меню видимости**: `/profile_visibility`
2. **Переключить видимость**: нажать на кнопку поля
3. **Просмотреть профиль**: `/profile` (отображаются только видимые поля)

### Примеры

**Скрыть личные данные:**

- Нажми на 🚫 возле **Вік** и **Вага**
- Твой профиль будет показывать только рост, пол и цель

**Показать всю информацию:**

- Нажимай на 🚫 поля, пока все не станут ✅
- Вся информация будет видна в `/profile`

Подробнее: [PROFILE_VISIBILITY_GUIDE.md](PROFILE_VISIBILITY_GUIDE.md)

## �🛠️ Обновления (v2.0)

### Исправленные проблемы

- ✅ Стабильность команды `/shop` (работала через раз)
- ✅ Синхронизация профиля после `/reset`
- ✅ Безопасность операций с монетами

### Улучшения

- 🔒 Потокобезопасное управление БД
- ⚡ Оптимизированные транзакции
- 📊 Лучшая обработка ошибок

Подробнее: [FIXES_APPLIED.md](FIXES_APPLIED.md)

## 🚀 Деплоймент на Heroku

```bash
# 1. Инициализировать Git репозиторий (если не сделано)
git init

# 2. Добавить файлы
git add .
git commit -m "Initial commit"

# 3. Создать Heroku приложение
heroku create your-app-name

# 4. Установить Config Vars
heroku config:set BOT_TOKEN=your_token
heroku config:set API_NINJAS_KEY=your_key
heroku config:set DEVELOPER_USERNAME=your_telegram_username

# 5. Запушить на Heroku
git push heroku main
```

`DEVELOPER_USERNAME` is the developer's Telegram username (without `@`). For local runs, add `DEVELOPER_USERNAME=your_telegram_username` to `.env`. If unset or invalid, the contact button is hidden and `/developer` displays a localized notice.

## 🐛 Решение проблем

### "ModuleNotFoundError: No module named 'aiogram'"

Убедитесь, что вы установили зависимости:

```bash
pip install -r requirements.txt
```

### "BOT_TOKEN is not set"

Проверьте, что файл `.env` существует и содержит правильный токен:

```bash
cat .env
```

### БД заблокирована

Это нормально при высокой нагрузке. Бот автоматически повторяет операцию с таймаутом 10 секунд.

## 📝 Лицензия

MIT License - используйте свободно!

## 👨‍💻 Контрибьютинг

Приветствуются pull requests! Для больших изменений сначала откройте issue.

## 📧 Поддержка

Если у вас есть вопросы, откройте issue на GitHub.

---

**Создано с ❤️ для фитнес-любителей**
