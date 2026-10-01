FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home gateway && mkdir /data && chown gateway:gateway /data
COPY workspace_gateway ./workspace_gateway
USER gateway
ENV WORKSPACE_GATEWAY_DATABASE=/data/workspace-gateway.sqlite3
EXPOSE 8090
CMD ["uvicorn", "workspace_gateway.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090", "--no-proxy-headers", "--no-access-log", "--ws-max-size", "2861744", "--limit-concurrency", "256"]
