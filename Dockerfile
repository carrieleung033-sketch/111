FROM python:3.12-slim
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && apt-get update -o APT::Update::Error-Mode=any && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py team.py providers.py editing.py ./
COPY web ./web
RUN useradd --uid 10001 --create-home studio && mkdir .runtime && chown studio:studio .runtime
USER studio
ENV BIND_HOST=0.0.0.0 PORT=8000 COOKIE_SECURE=1
EXPOSE 8000
VOLUME ["/app/.runtime"]
CMD ["python", "team.py"]
