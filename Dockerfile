FROM python:3.11-slim-bullseye as build

ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --target=/app/dependencies -r requirements.txt

FROM build as release

RUN useradd -m apprunner
USER apprunner

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app/dependencies"

WORKDIR /app
COPY --chown=apprunner: . /app

ARG PORT=5000
EXPOSE ${PORT}

CMD ["python", "main.py"]