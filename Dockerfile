FROM alpine:latest

WORKDIR /booktree
COPY requirements.txt .
RUN echo "**** installing system packages ****" \
    && apk update \
    && apk add --update --no-cache python3 py3-pip \
    && apk py3-pip \
    && apk add ffmpeg \
    && ln -sf python3 /usr/bin/python \      
    && pip install -r requirements.txt
 
COPY . /

VOLUME /config
VOLUME /logs
VOLUME /data/torrents/downloads
VOLUME /data/media/audiobooks/mam

COPY default_config.cfg /config/config.json

ENTRYPOINT ["python", "booktree.py", "--help"]