# DonationAlerts для Streamer.bot

Донаты из DonationAlerts приходят в Streamer.bot как триггер **DonationAlerts: Donation** с готовыми аргументами. Нужен Streamer.bot 1.0.x.

## Установка

1. Скачайте [`donationalerts.sb`](donationalerts.sb) из этого репозитория. В Streamer.bot: **Import** → выберите файл → **Import**.
   Появятся:
   - группа действий **DonationAlerts**: `DA | Code`, `DA | Connect`, `DA | Start`, `DA | Stop`, `DA | On donation`;
   - три чат-команды в группе **DonationAlerts**: `!daconnect`, `!dastart`, `!dastop`. Они импортируются **выключенными**.
2. Подключите DonationAlerts командой `!daconnect` (перезапускать Streamer.bot не нужно):
   1. Вкладка **Commands** → найдите **DA Connect** → включите её (галочка **Enabled**).
   2. Напишите `!daconnect` в чат своего канала (от своего аккаунта стримера).
   3. Откроется браузер со страницей подключения (на заполнение 10 минут):
      - создайте приложение на https://www.donationalerts.com/application/clients;
      - в поле **Redirect URL** укажите `http://127.0.0.1:8554/donationalerts/callback/`;
      - вставьте **ID** и **API key** приложения в форму и нажмите «Сохранить и авторизоваться»;
      - подтвердите доступ на DonationAlerts.
   4. После подтверждения приём донатов включится сам. В журнале появится `-- Donation Alerts: Connected`, затем `Started`.
   5. Команду **DA Connect** можно снова выключить.
3. Готово. Дальше приём донатов включается сам при каждом старте Streamer.bot.

Проверка: в DonationAlerts отправьте тестовое оповещение. В журнале Streamer.bot появится строка `-- Donation Alerts: <имя> <сумма> <валюта>: <сообщение>`.

## Команды

| Команда | Действие | Что делает |
| --- | --- | --- |
| `!daconnect` | **DA \| Connect** | останавливает приём, открывает страницу подключения, после авторизации снова запускает приём |
| `!dastart` | **DA \| Start** | запускает приём (если не подключено, сначала откроет страницу подключения) |
| `!dastop` | **DA \| Stop** | останавливает приём до `!dastart` или следующего старта Streamer.bot |

Как пользоваться: включите нужную команду на вкладке **Commands**, напишите её в чат, потом выключите обратно. Команды срабатывают только от стримера; сообщения от зрителей игнорируются, пока Streamer.bot сообщает их роль (Twitch). Держите команды выключенными, когда они не нужны.

Без команд тоже можно: при старте Streamer.bot страница подключения откроется сама, если интеграция ещё не подключена или авторизация устарела.
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
- Остановить приём: `!dastop` (см. «Команды»).

Внимание: экспорты и бэкапы Streamer.bot содержат ваши ключи и токены (глобальные переменные `daClientSecret`, `daAccessToken`, ...). Не выкладывайте их.

## Для разработчика

- `integration.cs` - весь код интеграции (один C# код в Streamer.bot).
- `tools/build_sb.py` - сборщик `.sb`; описание пакета в `tools/packages/donationalerts.json`, шаблоны формата экспорта 1.0.7 в `tools/golden/golden-1.0.7.sb` (действия, триггеры) и `tools/golden/command-1.0.7.json` (чат-команды, взяты из реального экспорта 1.0.7).
- `tools/compile_check.py` - офлайн-проверка компиляции под .NET Framework 4.8 (нужен .NET SDK); `tools/compile-check/` - проект и заглушка `CPH`, `tools/fixtures/compile/` - примеры для `--self-test`.

```
python -I tools/compile_check.py
python -I tools/build_sb.py build donationalerts --check
```

Результат: `donationalerts.sb` в корне репозитория. После изменения `integration.cs` пересоберите его и закоммитьте вместе с кодом.

Основано на форке интеграции play_code.
