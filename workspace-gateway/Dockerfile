FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home gateway && mkdir /data && chown gateway:gateway /data
COPY workspace_gateway ./workspace_gateway
USER gateway
ENV WORKSPACE_GATEWAY_DATABASE=/data/workspace-gateway.sqlite3
EXPOSE 8090
CMD ["python", "-m", "workspace_gateway.launcher"]
