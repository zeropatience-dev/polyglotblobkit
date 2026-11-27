FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY blob_filename_fix ./blob_filename_fix
COPY polyglotblobkit ./polyglotblobkit
RUN pip install --no-cache-dir '.[http,azure,s3]' && useradd --system --uid 10001 pbk
USER 10001
EXPOSE 8080
CMD ["uvicorn", "polyglotblobkit.http.deploy:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--workers", "1"]
