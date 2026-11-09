# The daily lines job (tools/lines_job.py) next to the program's file server. Built from the folder context.py makes
# (README.md); holds only the engine's Python files, the line providers and the job, nothing from private/ or work/.
# Pin the base at deploy time: BASE=python:3.13-slim@sha256:<the digest `docker pull python:3.13-slim` printed>.
ARG BASE=python:3.13-slim
FROM ${BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC HOME=/tmp XDG_DATA_HOME=/tmp
WORKDIR /app
COPY src/ /app/
USER 10001:10001
ENTRYPOINT ["python", "-I", "-B", "tools/lines_job.py"]
CMD ["serve", "--pack", "/files/datapack.json.gz", "--at", "10:00", "--archive", "/archive"]
