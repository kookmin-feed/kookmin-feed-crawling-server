#!/bin/bash

# 📤 ECR 배포 스크립트
# 빌드된 Docker 이미지들을 ECR에 배포

set -e

# 환경 변수 설정
STAGE=${1:-dev}
AWS_PROFILE="kookmin-feed"
AWS_REGION="ap-northeast-2"
ACCOUNT_ID="558793517018"
BUILD_INFO_FILE=".build-info-${STAGE}.txt"

echo "📤 ECR 배포 시작 - Stage: ${STAGE}"

# 빌드 정보 파일 확인
if [ ! -f "$BUILD_INFO_FILE" ]; then
    echo "❌ 빌드 정보 파일을 찾을 수 없습니다: ${BUILD_INFO_FILE}"
    echo "💡 먼저 이미지 빌드를 실행하세요:"
    echo "   ./scripts/build-images.sh ${STAGE}"
    exit 1
fi

# 빌드 정보 로드
echo "📋 빌드 정보 로드 중..."
# source 대신 직접 변수들을 설정
BUILD_TIME=$(grep "^BUILD_TIME=" "$BUILD_INFO_FILE" | cut -d'=' -f2)
STAGE=$(grep "^STAGE=" "$BUILD_INFO_FILE" | cut -d'=' -f2)
REPOSITORY_NAME=$(grep "^REPOSITORY_NAME=" "$BUILD_INFO_FILE" | cut -d'=' -f2)

# BUILT_IMAGES 배열을 직접 파싱
BUILT_IMAGES=()
while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*\"([^\"]+)\"[[:space:]]*$ ]]; then
        BUILT_IMAGES+=("${BASH_REMATCH[1]}")
    fi
done < <(sed -n '/^BUILT_IMAGES=(/,/^)/p' "$BUILD_INFO_FILE" | grep -E '^[[:space:]]*"[^"]+"[[:space:]]*$')

# ECR 로그인
echo "🔐 ECR 로그인 중..."
aws ecr get-login-password --region ${AWS_REGION} --profile ${AWS_PROFILE} | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# ECR 리포지토리 생성 (없는 경우)
echo "📦 ECR 리포지토리 확인/생성 중..."
aws ecr describe-repositories --repository-names ${REPOSITORY_NAME} --region ${AWS_REGION} --profile ${AWS_PROFILE} || \
aws ecr create-repository --repository-name ${REPOSITORY_NAME} --region ${AWS_REGION} --profile ${AWS_PROFILE}

# 각 이미지를 ECR에 푸시
echo ""
echo "📤 이미지들을 ECR에 푸시 중..."

DEPLOYED_IMAGES=()

for image_info in "${BUILT_IMAGES[@]}"; do
    IFS=':' read -r stage tag <<< "$image_info"
    
    echo ""
    echo "📦 ${stage} 이미지 ECR 푸시 중..."
    
    # ECR URI 생성
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:${stage}-${STAGE}"
    
    # ECR 태그 설정
    docker tag "${tag}" "${ECR_URI}"
    
    # ECR에 푸시
    if docker push "${ECR_URI}"; then
        echo "✅ ${stage} 이미지 ECR 푸시 성공: ${ECR_URI}"
        DEPLOYED_IMAGES+=("${stage}:${ECR_URI}")
    else
        echo "❌ ${stage} 이미지 ECR 푸시 실패"
        exit 1
    fi
done

echo ""
echo "🎉 모든 이미지 ECR 배포 완료!"
echo ""
echo "📋 배포된 이미지들:"
for image_info in "${DEPLOYED_IMAGES[@]}"; do
    IFS=':' read -r stage uri <<< "$image_info"
    echo "  - ${stage}: ${uri}"
done

# 배포 정보를 파일로 저장
DEPLOY_INFO_FILE=".deploy-info-${STAGE}.txt"
echo "# Deploy Info for ${STAGE}" > "$DEPLOY_INFO_FILE"
echo "DEPLOY_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_INFO_FILE"
echo "STAGE=${STAGE}" >> "$DEPLOY_INFO_FILE"
echo "AWS_REGION=${AWS_REGION}" >> "$DEPLOY_INFO_FILE"
echo "ACCOUNT_ID=${ACCOUNT_ID}" >> "$DEPLOY_INFO_FILE"
echo "REPOSITORY_NAME=${REPOSITORY_NAME}" >> "$DEPLOY_INFO_FILE"
echo "" >> "$DEPLOY_INFO_FILE"
echo "# Deployed Images" >> "$DEPLOY_INFO_FILE"
for image_info in "${DEPLOYED_IMAGES[@]}"; do
    IFS=':' read -r stage uri <<< "$image_info"
    echo "${stage}=${uri}" >> "$DEPLOY_INFO_FILE"
done

echo ""
echo "💾 배포 정보가 ${DEPLOY_INFO_FILE}에 저장되었습니다."
echo "🚀 Serverless 배포를 위해 다음 명령어를 실행하세요:"
echo "   serverless deploy --stage ${STAGE} --profile ${AWS_PROFILE}"
