# DonationAlerts для Streamer.bot

Донаты из DonationAlerts приходят в Streamer.bot как триггер **DonationAlerts: Donation** с готовыми аргументами. Нужен Streamer.bot 1.0.x.

## Установка

1. Скачайте [`donationalerts.sb`](donationalerts.sb) из этого репозитория. В Streamer.bot: **Import** → выберите файл → **Import**.
   Появится группа **DonationAlerts** с действиями `DA | Code`, `DA | Connect`, `DA | Start`, `DA | Stop`, `DA | On donation`.
2. **Перезапустите Streamer.bot.** При старте сам откроется браузер со страницей подключения (на заполнение 10 минут):
   - создайте приложение на https://www.donationalerts.com/application/clients;
   - в поле **Redirect URL** укажите `http://127.0.0.1:8554/donationalerts/callback/`;
   - вставьте **ID** и **API key** приложения в форму и нажмите «Сохранить и авторизоваться»;
   - подтвердите доступ на DonationAlerts.
3. Готово. Приём донатов включается сам при каждом старте Streamer.bot.

Проверка: в DonationAlerts отправьте тестовое оповещение. В журнале Streamer.bot появится строка `-- Donation Alerts: <имя> <сумма> <валюта>: <сообщение>`.

## Как запускается подключение (Connect)

Отдельно запускать ничего не нужно:

- при старте Streamer.bot действие **DA | Start** само открывает страницу подключения, если интеграция ещё не подключена;
- если авторизация устарела и не обновилась сама, страница подключения тоже откроется при старте.

Если окно подключения закрылось раньше времени, просто перезапустите Streamer.bot.

### Команда `!daconnect` (по желанию)

Чтобы переподключаться без перезапуска Streamer.bot, повесьте на **DA | Connect** чат-команду. Это делается один раз:

1. Вкладка **Commands** → правый клик → **Add**.
2. Name: `DA Connect`, Commands: `!daconnect`, в **Permissions** оставьте только себя (Broadcaster), чтобы зрители не могли её вызвать. Нажмите **OK**.
3. Вкладка **Actions** → действие **DA | Connect** → панель **Triggers** → правый клик → **Add** → **Core** → **Commands** → **Command Triggered** → выберите `DA Connect` → **OK**.

Теперь `!daconnect` в чате останавливает приём, открывает страницу подключения и после авторизации снова запускает приём.

Таким же способом можно сделать команды для **DA | Start** (`!dastart`) и **DA | Stop** (`!dastop`).

## Как реагировать на донат

Добавляйте свои под-действия (сообщение в чат, TTS, OBS и т.д.) в действие **DA | On donation**. Можно также повесить триггер **Custom** → **DonationAlerts** → **DonationAlerts: Donation** на любое своё действие.

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

Пример сообщения в чат: под-действие **Twitch** → **Chat** → **Send Message to Channel** с текстом `%daUsername% задонатил %daAmount% %daCurrency%: %daMessage%`.

Обновления целей приходят триггером **DonationAlerts: Goal updated** (`%daGoalTitle%`, `%daGoalCurrent%`, `%daGoalTarget%`, `%daGoalCurrency%`).

## Если что-то не работает

- Redirect URL в приложении DonationAlerts должен совпадать точно, со слешем в конце.
- Порт 8554 должен быть свободен, пока открыта страница подключения.
- Ошибки ищите в журнале Streamer.bot по строкам `-- Donation Alerts:`.
- Сменить аккаунт или приложение: `!daconnect`, либо удалите глобальные переменные `daAccessToken` и `daRefreshToken` (Variables → Global Variables → Persisted) и перезапустите Streamer.bot. Для смены ID/API key удалите также `daClientId` и `daClientSecret`.
- Остановить приём: **DA | Stop** (через команду, см. выше).

Внимание: экспорты и бэкапы Streamer.bot содержат ваши ключи и токены (глобальные переменные `daClientSecret`, `daAccessToken`, ...). Не выкладывайте их.

## Для разработчика

- `integration.cs` - весь код интеграции (один C# код в Streamer.bot).
- `tools/build_sb.py` - сборщик `.sb`; описание пакета в `tools/packages/donationalerts.json`, шаблон формата экспорта 1.0.7 в `tools/golden/golden-1.0.7.sb`.
- `tools/compile_check.py` - офлайн-проверка компиляции под .NET Framework 4.8 (нужен .NET SDK); `tools/compile-check/` - проект и заглушка `CPH`, `tools/fixtures/compile/` - примеры для `--self-test`.

```
python -I tools/compile_check.py
python -I tools/build_sb.py build donationalerts --check
```

Результат: `donationalerts.sb` в корне репозитория. После изменения `integration.cs` пересоберите его и закоммитьте вместе с кодом.

Основано на форке интеграции play_code.
