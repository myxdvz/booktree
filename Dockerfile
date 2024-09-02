FROM alpine:latest

ARG UID
ARG GID
ARG USER
ARG GROUPNAME
ENV USER=${USER}
ENV GROUPNAME=${GROUPNAME}
ENV UID=${UID}
ENV GID=${GID}

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
    && pip install --no-cache-dir --requirement /booktree-main/requirements.txt \
    && pip install --upgrade pip \
    && rm -rf booktree \
    && mv booktree-main booktree \
    && if getent passwd ${UID} >/dev/null; then deluser $(getent passwd ${UID} | cut -d: -f1); fi \
    && if getent group ${GID} >/dev/null; then delgroup $(getent group ${GID} | cut -d: -f1); fi \
    && addgroup --system --gid ${GID} ${GROUPNAME} \
    && adduser --system --uid ${UID} --disabled-password --gecos "" --ingroup ${GROUPNAME} --no-create-home ${USER} \
    && chown -R ${UID}:${GID} /booktree

USER ${USER}
WORKDIR /booktree 
VOLUME /config
VOLUME /logs
VOLUME /data
