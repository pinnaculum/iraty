FROM alpine:3.16

RUN apk update
RUN apk add --no-cache python3 py3-pip git

RUN mkdir -p /usr/local/src/iraty
COPY . /usr/local/src/iraty

RUN cd /usr/local/src/iraty && pip install -e .

ENTRYPOINT ["iraty"]
