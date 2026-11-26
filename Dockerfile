ARG PYTHON_IMAGE=python:3.11-alpine@sha256:7fbad8e4652eae0186429a6f26cf5b23e27e8c6fd7ac4d0cfd7a6988cdeea1e1

FROM ${PYTHON_IMAGE} AS dependencies
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
WORKDIR /build
COPY requirements-api.txt ./requirements-api.txt
RUN python -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir --require-hashes -r requirements-api.txt \
    && pip uninstall --yes pip setuptools wheel

FROM ${PYTHON_IMAGE} AS runtime
RUN apk add --no-cache krb5-libs=1.22.3-r0 \
    && python -m pip uninstall --yes pip setuptools wheel
ARG IMAGE_VERSION=0.1.0
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.title="GroundStack API" \
      org.opencontainers.image.description="GroundStack process API and static workspace preview" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      org.opencontainers.image.revision="${SOURCE_REVISION}" \
      org.opencontainers.image.source="https://github.com/mangopep/GroundStack"
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 web ./web
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
