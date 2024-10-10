FROM alpine:latest

ARG UID
ARG GID
ARG USER
ARG GROUPNAME
ENV USER=${USER}
ENV GROUPNAME=${GROUPNAME}
ENV UID=${UID}
ENV GID=${GID}

WORKDIR /booktree 
RUN echo "**** installing system packages ****" \
    && apk update \
    && apk add --update --no-cache python3 py3-pip \
    && apk add py3-pip \
    && apk add ffmpeg \
    && ln -sf python3 /usr/bin/python \   
    && mkdir -p /venv \
    && python -m venv /venv \
    && source /venv/bin/activate \ 
    && pip install --upgrade pip \
    && if getent passwd ${UID} >/dev/null; then deluser $(getent passwd ${UID} | cut -d: -f1); fi \
    && if getent group ${GID} >/dev/null; then delgroup $(getent group ${GID} | cut -d: -f1); fi \
    && addgroup --system --gid ${GID} ${GROUPNAME} \
    && adduser --system --uid ${UID} --disabled-password --gecos "" --ingroup ${GROUPNAME} --no-create-home ${USER} \
    && chown -R ${UID}:${GID} /booktree

USER ${USER}
VOLUME /config
VOLUME /logs
VOLUME /data
