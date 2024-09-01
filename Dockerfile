FROM alpine:latest

RUN echo "**** installing system packages ****" \
    && apk update \
    && apk add --update --no-cache python3 py3-pip \
    && apk add py3-pip \
    && apk add ffmpeg \
    && ln -sf python3 /usr/bin/python \   
    && mkdir -p /venv \
    && python -m venv /venv \
    && source /venv/bin/activate \ 
    && wget -O /booktree https://github.com/myxdvz/booktree/archive/refs/heads/main.zip \
    && chmod +x /booktree \
    && unzip /booktree \
    && pip install --upgrade pip \
    && pip install --no-cache-dir --requirement /booktree-main/requirements.txt \
    && rm -rf booktree \
    && mv booktree-main booktree

WORKDIR /booktree 
VOLUME /config
VOLUME /logs
VOLUME /data

COPY default_config.cfg /config/config.json