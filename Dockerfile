# 🚀 Kookmin Feed Dynamic Scrapers - Multi-Target Docker Build
# 동적 웹 스크래핑이 필요한 여러 스크래퍼를 지원하는 확장 가능한 Docker 이미지

# ====================
# Stage 1: Base Image (공통 환경) - 최신 Lambda 이미지 사용
# ====================
FROM public.ecr.aws/lambda/python:3.12 AS base

# 필수 런타임 라이브러리 설치
RUN dnf install -y \
        nss \
        nspr \
        dejavu-sans-fonts \
        dbus \
        atk \
        at-spi2-atk \
        at-spi2-core \
        libX11 \
        libXcomposite \
        libXdamage \
        libXext \
        libXfixes \
        libXrandr \
        mesa-libgbm \
        libxcb \
        libxkbcommon \
        systemd-libs \
        alsa-lib && \
    dnf clean all

# Python 의존성 설치
COPY requirements.txt .
RUN pip install -r requirements.txt

# 브라우저 경로를 이미지의 영속 레이어로 고정
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright && chmod -R 0755 /ms-playwright

# !!! 중요: /tmp 사용 금지. 기본 경로(/ms-playwright)에 브라우저를 이미지에 굽기
# 시스템 라이브러리는 이미 설치했으므로 브라우저만 설치
RUN python -m playwright install chromium --force

# 공통 유틸리티 및 메타데이터 복사
COPY common_utils.py ${LAMBDA_TASK_ROOT}/
COPY master_utils.py ${LAMBDA_TASK_ROOT}/
COPY metadata/ ${LAMBDA_TASK_ROOT}/metadata/

# ====================
# Stage 2: Library General Scraper
# ====================
FROM base AS library-general
COPY lambda_web_scraper/library_general_handler.py ${LAMBDA_TASK_ROOT}/lambda_web_scraper/
CMD ["lambda_web_scraper.library_general_handler.handler"]