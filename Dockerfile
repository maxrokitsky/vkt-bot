FROM python:3.13

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false

ENV POETRY_HOME=/opt/poetry
ENV VENV_HOME=/opt/venv

RUN apt-get update && apt-get install --no-install-recommends -y \
    # deps for installing poetry
    curl \
    # deps for building python deps
    build-essential

RUN python3 -m venv $VENV_HOME

RUN $VENV_HOME/bin/python3 -m venv $POETRY_HOME
RUN $POETRY_HOME/bin/pip install poetry
ENV PATH=$VENV_HOME/bin:$POETRY_HOME/bin:$PATH

WORKDIR /app

COPY . /app

RUN which python
RUN poetry install --without dev --sync

ENTRYPOINT ["poetry", "run"]

CMD ["python", "/app/teams_bot/main.py"]
