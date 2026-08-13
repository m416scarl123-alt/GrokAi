# GrokChat — Telegram AI bot

Публичный Telegram-бот на Grok 4.5 с закрытой активацией, памятью, веб-поиском,
анализом изображений, голосовыми сообщениями, TTS, генерацией изображений,
PostgreSQL и админ-панелью.

## Реализовано
- /start
- закрытая активация ключом
- один ключ: до 3 активаций
- бессрочный доступ
- память последних 25 сообщений
- /newchat, /clear
- Grok 4.5
- web search для полного доступа
- анализ изображений
- voice -> STT -> Grok
- ответ голосом по запросу: /voice on|off
- генерация изображений: /image ...
- /admin с подтверждением одноразовым кодом по Gmail
- создание/отзыв ключей
- /nonstop @username для полного доступа
- PostgreSQL
- Docker Compose для VPS

## Запуск на VPS
1. Скопируй .env.example в .env.
2. Заполни секреты.
3. Выполни: docker compose up -d --build
4. Логи: docker compose logs -f bot

## Gmail
Используй Gmail App Password, а не обычный пароль Google. Для App Password
нужна включённая 2-Step Verification.

## Безопасность
Не отправляй Telegram Bot Token, XAI API Key или Gmail App Password в чат.
Храни их только в .env на VPS.

## 70% / 100%
В этой стартовой версии full_access=false означает 70%, а /nonstop включает
100%. Набор расширенных функций можно изменить в bot.py.
