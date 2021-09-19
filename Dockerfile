# syntax=docker/dockerfile:1

FROM python:3.9

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt
EXPOSE 8080

CMD ["sh" , "-c", "./tgp.py --port=8080 --host=0.0.0.0 --debug \"$TGPROXY_CHANNEL\""]
