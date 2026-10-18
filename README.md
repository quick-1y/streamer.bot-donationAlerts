# DonationAlerts для Streamer.bot

Донаты из DonationAlerts приходят в Streamer.bot как триггер **DonationAlerts: Donation** с готовыми аргументами.

## Установка

1. В Streamer.bot: **Import** → выберите файл `donationalerts.sb` → Import.
   Появится группа **DonationAlerts** с действиями `DA | Code`, `DA | Connect`, `DA | Start`, `DA | Stop`, `DA | On donation`.
2. Перезапустите Streamer.bot. При старте сам откроется браузер со страницей подключения (10 минут на заполнение):
   - создайте приложение на https://www.donationalerts.com/application/clients;
   - в поле Redirect URL укажите `http://127.0.0.1:8554/donationalerts/callback/`;
   - вставьте ID и API key приложения в форму и нажмите «Сохранить и авторизоваться»;
   - подтвердите доступ на DonationAlerts.
3. Всё. Приём донатов включается сам при каждом старте Streamer.bot. Если окно подключения закрылось раньше времени, просто перезапустите Streamer.bot ещё раз.

Проверка: в DonationAlerts отправьте тестовое оповещение. В журнале Streamer.bot появится строка `-- Donation Alerts: <имя> <сумма> <валюта>: <сообщение>`.

## Как реагировать на донат

Добавляйте свои под-действия (сообщение в чат, TTS, OBS и т.д.) в действие **DA | On donation**. Можно также повесить триггер **Custom → DonationAlerts → DonationAlerts: Donation** на любое своё действие.

Аргументы:

| Аргумент | Что это |
| --- | --- |
| `%daUsername%` | имя донатера (`Anonymous`, если не указано) |
| `%daAmount%` | сумма, как пришла (`100`, `22.5`) |
| `%daAmountNumber%` | сумма числом, для If/Else |
| `%daCurrency%` | валюта (`RUB`, `USD`, ...) |
| `%daAmountConverted%` | сумма в вашей валюте |
| `%daMessage%` | текст сообщения |
| `%daType%` | `text` или `audio` |
| `%daAudioUrl%`, `%daAudio%` | ссылка на аудио-сообщение и путь к скачанному файлу |
| `%daDonationId%`, `%daCreatedAt%` | id и время доната |

Обновления целей приходят триггером **DonationAlerts: Goal updated** (`%daGoalTitle%`, `%daGoalCurrent%`, `%daGoalTarget%`, `%daGoalCurrency%`).

## Если что-то не работает

- Redirect URL в приложении DonationAlerts должен совпадать точно, со слешем в конце.
- Порт 8554 должен быть свободен во время **DA | Connect**.
- Авторизация слетела: удалите глобальную переменную `daAccessToken` и перезапустите Streamer.bot.
- Остановить приём: **DA | Stop**.

Внимание: экспорты и бэкапы Streamer.bot содержат ваши ключи и токены (глобальные переменные `daClientSecret`, `daAccessToken`, ...). Не выкладывайте их.

## Для разработчика

Код интеграции в `integration.cs`. Пакет собирается командой:

```
python -I tools/build_sb.py build donationalerts --check
```

Результат: `dist/donationalerts.sb`. Офлайн-проверка компиляции: `python -I tools/compile_check.py`.

Основано на версии play_code.
