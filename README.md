# MyTelegramBot 🏋️

Умный Telegram бот для отслеживания физических тренировок, управления профилем и магазина награды с монетной системой.

## 🚀 Возможности

- 📊 **Отслеживание тренировок** - логирование упражнений и их результатов
- 📝 **Персональная программа** - создание недельного плана по цели, доступному времени и оборудованию
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

Telegram command menu містить лише основні команди. Додаткові slash-команди залишаються сумісними; також їхні функції доступні через кнопки головного меню. Мову можна змінити в **Налаштуваннях → Мова**.

The Telegram command menu contains only the core commands. Additional slash commands remain supported, and their features are also available from the main-menu buttons. Change the interface language in **Settings → Language**.

### Українська

| Команда меню | Призначення |
| --- | --- |
| `/start` | Відкрити головне меню |
| `/help` | Довідка та навігація ботом |
| `/workout` | Записати тренування |
| `/today` | Переглянути активність за сьогодні |
| `/stats` | Статистика та прогрес |
| `/history` | Історія тренувань |
| `/program` | Створити або переглянути програму тренувань |

### English

| Menu command | Purpose |
| --- | --- |
| `/start` | Open the main menu |
| `/help` | Help and bot navigation |
| `/workout` | Record a workout |
| `/today` | View today's activity |
| `/stats` | Stats and progress |
| `/history` | Workout history |
| `/program` | Create or view a training plan |

### Додаткові команди та можливості

| Команди | Можливість |
| --- | --- |
| `/weight`, `/weight_stats` | Додати вагу, переглянути записи та графік |
| `/level`, `/chart` | Рівень, XP і графіки прогресу |
| `/profile`, `/edit_profile`, `/profile_visibility` | Перегляд і налаштування профілю |
| `/goal`, `/set_goal` | Перегляд і зміна тижневої цілі |
| `/daily`, `/challenge` | Щоденне завдання та окремі челенджі |
| `/suggest`, `/motivate`, `/tip` | Запропоновані тренування, мотивація й поради |
| `/shop`, `/wallet`, `/use` | Магазин, монети, інвентар і використання предметів |
| `/reminders` | Керування нагадуваннями |
| `/export`, `/import`, `/reset` | Експорт, імпорт і скидання даних; небезпечні дії потребують підтвердження |
| `/change_language` | Перемкнути українську й англійську |
| `/developer` | Зв’язатися з розробником |

Команди `/admin` і `/backup` доступні лише ID з `ADMIN_IDS`.

### Additional commands and features

| Commands | Feature |
| --- | --- |
| `/weight`, `/weight_stats` | Add weight entries, review them, and open the chart |
| `/level`, `/chart` | Level, XP, and progress charts |
| `/profile`, `/edit_profile`, `/profile_visibility` | View and manage your profile |
| `/goal`, `/set_goal` | View and change the weekly goal |
| `/daily`, `/challenge` | Daily task and separate challenges |
| `/suggest`, `/motivate`, `/tip` | Suggested workouts, motivation, and tips |
| `/shop`, `/wallet`, `/use` | Shop, coins, inventory, and item use |
| `/reminders` | Manage reminders |
| `/export`, `/import`, `/reset` | Export, import, and reset data; destructive actions require confirmation |
| `/change_language` | Switch between Ukrainian and English |
| `/developer` | Contact the developer |

`/admin` and `/backup` are available only to IDs in `ADMIN_IDS`.

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
heroku config:set DEVELOPER_CHAT_ID=123456789

# 5. Запушить на Heroku
git push heroku main
```

`DEVELOPER_CHAT_ID` is the developer's private Telegram chat ID. For local runs, add `DEVELOPER_CHAT_ID=123456789` to `.env`; for Heroku, set it as a Config Var. If unset or invalid, feedback submission is disabled and `/developer` displays a localized notice. Keep the bot chat private so only the developer can use ticket actions.

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
