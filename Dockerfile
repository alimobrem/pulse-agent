FROM registry.access.redhat.com/ubi9/python-312:latest
WORKDIR /opt/app-root/src

# Install dependencies (cached when pyproject.toml unchanged)
COPY pyproject.toml .
RUN pip install anthropic[vertex] kubernetes rich fastapi uvicorn[standard] websockets

# Copy source and install package (force-reinstall ensures latest source)
COPY sre_agent/ sre_agent/
RUN pip install --no-deps --force-reinstall .

USER 1001
EXPOSE 8080
CMD ["pulse-agent-api"]
