
FROM python:3.10-slim AS build-env
RUN mkdir -p /app
WORKDIR /app
RUN --mount=type=bind,source=uv.lock,target=/app/uv.lock \
    --mount=type=bind,source=pyproject.toml,target=/app/pyproject.toml \
    pip install uv \
    && uv sync --frozen --no-install-project
COPY . /app
RUN uv sync --frozen --python-preference=system
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
# Deployment environment variables
ENV PORT=8000
ENV DEBUG=0
ENV DATABASE_URL=""
ENV SENDGRID_API_KEY=""
ENV FROM_NUMBER=""
ENV TWILIO_SSID=""
ENV TWILIO_AUTH_TOKEN=""
RUN /app/.venv/bin/python manage.py collectstatic
# TODO: Migrations?
CMD /app/.venv/bin/granian --host 0.0.0.0 --port $PORT --log-level=debug --interface wsgi drover.wsgi:application
