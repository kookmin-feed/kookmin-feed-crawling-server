#!/bin/bash

# 🐳 Multi-Target Docker 이미지 빌드 스크립트
# Dockerfile의 모든 stage를 자동으로 감지하여 이미지 빌드

set -e

# 환경 변수 설정
STAGE=${1:-dev}
REPOSITORY_NAME="kookmin-feed-crawling-server"
DOCKERFILE_PATH="Dockerfile"

echo "🚀 Multi-Target Docker 이미지 빌드 시작 - Stage: ${STAGE}"

# Dockerfile에서 모든 stage 추출
echo "🔍 Dockerfile에서 stage 분석 중..."
STAGES=($(grep -E "^FROM.*AS" "$DOCKERFILE_PATH" | sed 's/.*AS //'))

if [ ${#STAGES[@]} -eq 0 ]; then
    echo "❌ Dockerfile에서 stage를 찾을 수 없습니다."
    exit 1
fi

echo "📋 발견된 stage들:"
for stage in "${STAGES[@]}"; do
    echo "  - ${stage}"
done

# 각 stage별로 이미지 빌드
echo ""
echo "🐳 각 stage별 Docker 이미지 빌드 중..."

BUILT_IMAGES=()

for stage in "${STAGES[@]}"; do
    echo ""
    echo "📦 ${stage} 이미지 빌드 중..."
    
    # 이미지 태그 생성
    IMAGE_TAG="${REPOSITORY_NAME}:${stage}-${STAGE}"
    
    # Docker 빌드 실행 (Lambda 호환 아키텍처로 강제 빌드)
    if docker build --platform linux/amd64 --target "${stage}" -t "${IMAGE_TAG}" .; then
        echo "✅ ${stage} 이미지 빌드 성공: ${IMAGE_TAG}"
        BUILT_IMAGES+=("${stage}:${IMAGE_TAG}")
    else
        echo "❌ ${stage} 이미지 빌드 실패"
        exit 1
    fi
done

echo ""
echo "🎉 모든 이미지 빌드 완료!"
echo ""
echo "📋 빌드된 이미지들:"
for image_info in "${BUILT_IMAGES[@]}"; do
    IFS=':' read -r stage tag <<< "$image_info"
    echo "  - ${stage}: ${tag}"
done

# 빌드된 이미지 정보를 파일로 저장 (ECR 배포 스크립트에서 사용)
BUILD_INFO_FILE=".build-info-${STAGE}.txt"
echo "# Build Info for ${STAGE}" > "$BUILD_INFO_FILE"
echo "BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$BUILD_INFO_FILE"
echo "STAGE=${STAGE}" >> "$BUILD_INFO_FILE"
echo "REPOSITORY_NAME=${REPOSITORY_NAME}" >> "$BUILD_INFO_FILE"
echo "" >> "$BUILD_INFO_FILE"
echo "# Built Images" >> "$BUILD_INFO_FILE"
for image_info in "${BUILT_IMAGES[@]}"; do
    IFS=':' read -r stage tag <<< "$image_info"
    echo "${stage}=${tag}" >> "$BUILD_INFO_FILE"
done

# ECR 배포 스크립트에서 사용할 수 있도록 BUILT_IMAGES 배열도 저장
echo "" >> "$BUILD_INFO_FILE"
echo "# BUILT_IMAGES array for ECR deployment" >> "$BUILD_INFO_FILE"
echo "BUILT_IMAGES=(" >> "$BUILD_INFO_FILE"
for image_info in "${BUILT_IMAGES[@]}"; do
    echo "    \"${image_info}\"" >> "$BUILD_INFO_FILE"
done
echo ")" >> "$BUILD_INFO_FILE"

echo ""
echo "💾 빌드 정보가 ${BUILD_INFO_FILE}에 저장되었습니다."
echo "🚀 ECR 배포를 위해 다음 명령어를 실행하세요:"
echo "   ./scripts/deploy-to-ecr.sh ${STAGE}"
