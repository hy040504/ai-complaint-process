FROM python:3.12-slim-bookworm
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu
COPY rag/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
WORKDIR /workspace
ENTRYPOINT ["python", "-m", "rag"]
