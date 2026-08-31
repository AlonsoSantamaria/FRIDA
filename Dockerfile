FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY ["docs/History docs & images/FRIDA_flower_icon_actual.png", "/app/branding/frida-flower-icon.png"]
COPY migrations ./migrations
COPY data/frida-final-london-appraisal.sqlite3 /app/seed/frida-final-london-appraisal.sqlite3
COPY data/source-validation/wp01/denue/raw/denue_22_0525_csv.zip /app/evidence/denue_22_0525_csv.zip
COPY data/source-validation/wp01/denue/raw/denue_22_0526_corrected_csv.zip /app/evidence/denue_22_0526_corrected_csv.zip
# Native Vertex structured-output adapters import ``google.genai`` at runtime.
# Install the approved Google runtime extra in the deployed image; installing
# the base package alone intentionally omits this optional local capability.
RUN pip install --no-cache-dir ".[google-runtime]"
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME ["/data"]
CMD ["python", "-m", "frida.staging"]
