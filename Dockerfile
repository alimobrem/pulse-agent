FROM registry.access.redhat.com/ubi9/python-312:latest
WORKDIR /opt/app-root/src
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY sre_agent/ sre_agent/
RUN pip install --no-cache-dir --no-deps .
USER 1001
EXPOSE 8080
CMD ["pulse-agent-api"]
