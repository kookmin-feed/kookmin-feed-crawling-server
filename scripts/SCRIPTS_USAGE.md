# 🚀 Docker & ECR 배포 스크립트 사용법

## 📋 개요

이 프로젝트는 **Multi-Target Dockerfile**을 사용하여 동적 웹 스크래핑이 필요한 여러 스크래퍼를 효율적으로 관리하는 스크립트들을 제공합니다.

## 🛠️ 제공 스크립트

### 1. **`scripts/build-images.sh`** - Docker 이미지 빌드
- Dockerfile의 모든 stage를 자동으로 감지
- 각 stage별로 독립적인 이미지 생성
- 빌드 정보를 파일로 저장

### 2. **`scripts/deploy-to-ecr.sh`** - ECR 배포
- 빌드된 이미지들을 ECR에 자동 배포
- 빌드 정보 파일을 기반으로 동작
- 배포 정보를 파일로 저장

### 3. **`scripts/deploy-all.sh`** - 통합 배포
- 빌드 → ECR 배포 → Serverless 배포까지 전체 과정 실행
- 각 단계별 성공/실패 확인

## 🚀 사용법

### **전체 과정 한 번에 실행**
```bash
# 스크립트 실행 권한 부여
chmod +x scripts/*.sh

# 전체 배포 (dev 환경)
./scripts/deploy-all.sh dev

# 전체 배포 (prod 환경)
./scripts/deploy-all.sh prod
```

### **단계별 실행**

#### 1단계: 이미지 빌드만
```bash
./scripts/build-images.sh dev
```

#### 2단계: ECR 배포만 (빌드 후)
```bash
./scripts/deploy-to-ecr.sh dev
```

#### 3단계: Serverless 배포만
```bash
serverless deploy --stage dev --profile kookmin-feed
```

## 🔍 스크립트 동작 원리

### **자동 Stage 감지**
```bash
# Dockerfile에서 모든 stage 추출
STAGES=($(grep -E "^FROM.*as" "Dockerfile" | sed 's/.*as //'))

# 결과 예시:
# - base
# - library-general
# - future-mobility
# - architecture-academic
# - custom-scraper
```

### **동적 이미지 생성**
```bash
# 각 stage별로 이미지 생성
for stage in "${STAGES[@]}"; do
    docker build --target "${stage}" -t "${REPOSITORY_NAME}:${stage}-${STAGE}" .
done
```

### **자동 ECR 배포**
```bash
# 각 이미지를 ECR에 푸시
for stage in "${STAGES[@]}"; do
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPOSITORY_NAME}:${stage}-${STAGE}"
    docker tag "${tag}" "${ECR_URI}"
    docker push "${ECR_URI}"
done
```

## ➕ 새로운 스크래퍼 추가 시

### **1. Dockerfile에 Stage 추가**
```dockerfile
# ====================
# Stage N: New Scraper
# ====================
FROM base as new-scraper
COPY lambda_web_scraper/new_scraper_handler.py ${LAMBDA_TASK_ROOT}/lambda_web_scraper/
CMD ["lambda_web_scraper.new_scraper_handler.handler"]
```

### **2. 자동으로 처리됨**
- **빌드 스크립트**: 새로운 stage를 자동으로 감지하여 이미지 생성
- **ECR 배포**: 새로운 이미지를 자동으로 ECR에 푸시
- **별도 설정 불필요**: 스크립트 수정 없이 자동 처리

## 📊 생성되는 파일들

### **빌드 정보 파일**
```
.build-info-{STAGE}.txt
├── BUILD_TIME: 빌드 시간
├── STAGE: 환경 (dev/prod)
├── REPOSITORY_NAME: 이미지 이름
└── BUILT_IMAGES: 빌드된 이미지 목록
```

### **배포 정보 파일**
```
.deploy-info-{STAGE}.txt
├── DEPLOY_TIME: 배포 시간
├── STAGE: 환경 (dev/prod)
├── AWS_REGION: AWS 리전
├── ACCOUNT_ID: AWS 계정 ID
├── REPOSITORY_NAME: ECR 리포지토리 이름
└── DEPLOYED_IMAGES: 배포된 이미지 목록
```

## 🚨 주의사항

1. **순서 준수**: 빌드 → ECR 배포 → Serverless 배포 순서로 실행
2. **권한 확인**: AWS CLI와 Docker 실행 권한 확인
3. **프로필 설정**: `kookmin-feed` AWS 프로필 설정 확인
4. **리소스 정리**: `.build-info-*.txt`, `.deploy-info-*.txt` 파일은 필요시 삭제

## 🆘 문제 해결

### **빌드 실패 시**
```bash
# 캐시 제거 후 재빌드
docker build --no-cache --target library-general -t scraper:library-general .
```

### **ECR 로그인 실패 시**
```bash
# AWS 프로필 확인
aws sts get-caller-identity --profile kookmin-feed

# ECR 로그인 재시도
aws ecr get-login-password --region ap-northeast-2 --profile kookmin-feed | docker login --username AWS --password-stdin 558793517018.dkr.ecr.ap-northeast-2.amazonaws.com
```

### **Serverless 배포 실패 시**
```bash
# 로그 확인
sls logs -f library_general_scraper --stage dev

# 함수 상태 확인
sls info --stage dev
```

## 🎯 장점

1. **자동화**: Dockerfile 수정 시 자동으로 모든 stage 처리
2. **확장성**: 새로운 스크래퍼 추가 시 스크립트 수정 불필요
3. **안정성**: 각 단계별 성공/실패 확인
4. **추적성**: 빌드 및 배포 정보를 파일로 저장
5. **유연성**: 단계별 또는 전체 과정 실행 가능
