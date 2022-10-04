# pull the official docker image
FROM python:3.10.4-slim

ENV WORKDIR=/app
ENV USER=app
ENV APP_HOME=/home/app/web
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR $WORKDIR

# install gcc (for pandas, sigh)
RUN apt-get -y update && apt-get -y install gcc g++
COPY ./requirements.txt $WORKDIR/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN adduser --system --group $USER
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY . $APP_HOME
RUN chown -R $USER:$USER $APP_HOME
USER $USER
