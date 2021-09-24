# Асинхронный прокси для Телеграмма

Принимает сообщения по http-протоколу, ставит в очередь и асинхронно отправляет в телеграмм с ретраями.

В командной строке принимает описание каналов в формате url и необязательные хост и порт.

Формат url канала:
```
telegram://bot:token@chat_id/channel_name?timeout=3&&send_banner_on_startup=0

timeout — необязательный настраиваемый параметр таймаута для АПИ телеграма
send_banner_on_startup=0 — не отправлять в канал сообщение при старте обработчика очереди
```

## Запустить сервер

`pipenv run tgp.py telegram://bot:tok1@123/chat_1 telegram://bot:tok1@123/chat_2`

## API

```
Get ping-status — GET http://localhost:5000/ping.html
Get channels list — GET http://localhost:5000/
Send messge POST http://localhost:5000/chat_1 (text="Message", parse_mode ...)
Get channel statistics GET http://localhost:5000/chat_1
```
