FROM python:3.10-slim AS build-env
RUN mkdir -p /app
WORKDIR /app
COPY uv.lock /app/uv.lock
COPY pyproject.toml /app/pyproject.toml
RUN pip install uv \
    && uv sync --frozen --no-install-project
COPY . /app
RUN uv sync --frozen --python-preference=system
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
# Deployment environment variables
# ENV PORT=8000
# ENV DEBUG=0
# ENV DATABASE_URL=""
# ENV SENDGRID_API_KEY=""
# ENV FROM_NUMBER=""
# ENV TWILIO_SSID=""
# ENV TWILIO_AUTH_TOKEN=""
# NOTE: Setting all these required environment variables to empty so that `collectstatic` succeeds.
RUN DATABASE_URL="" SENDGRID_API_KEY="" FROM_NUMBER="" TWILIO_SSID="" TWILIO_AUTH_TOKEN="" /app/.venv/bin/python manage.py collectstatic
CMD /app/.venv/bin/python manage.py migrate && \
    /app/.venv/bin/granian --host 0.0.0.0 --port $PORT --log-level=debug --interface wsgi drover.wsgi:application
