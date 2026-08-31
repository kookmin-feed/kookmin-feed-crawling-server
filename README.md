# 국민대학교 피드 크롤링 서버

이 프로젝트는 국민대학교의 공지사항, RSS 피드, 공모전 정보를 크롤링하여 새로운 공지사항을 확인하고 데이터베이스에 저장하는 서버입니다.

## 주요 기능

- **공지사항 크롤링**: 다양한 소스(예: RSS 피드, 웹사이트)에서 공지사항을 수집합니다.
- **중복 확인**: 기존 데이터와 비교하여 새로운 공지사항만 저장합니다.
- **데이터베이스 관리**: MongoDB를 사용하여 공지사항 데이터를 저장 및 관리합니다.
- **로깅**: 크롤링 및 데이터 처리 과정에서 발생하는 이벤트를 로깅합니다.

## 기술 스택

- **언어**: Python
- **웹 크롤링**: BeautifulSoup, feedparser
- **비동기 처리**: asyncio
- **데이터베이스**: MongoDB
- **로깅**: Python `logging` 모듈
- **환경 변수 관리**: `.env` 파일

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음과 같은 환경 변수를 설정하세요:

```
IS_PROD=True
MONGO_URI=mongodb://localhost:27017
```

### 3. 데이터베이스 초기화

스크래퍼 메타데이터를 초기화하려면 다음 명령어를 실행하세요:

```bash
python -m utils.check_new_scraper
```

### 4. 서버 실행

```bash
python main.py
```

## 주요 파일 설명

- **`main.py`**: 서버의 진입점으로, 크롤링 작업을 관리합니다.
- **`utils/web_scraper.py`**: 웹 스크래퍼의 추상 클래스 및 공통 로직을 정의합니다.
- **`web_scraper/rss_notice_scraper.py`**: RSS 피드에서 공지사항을 크롤링하는 클래스입니다.
- **`config/logger_config.py`**: 로깅 설정을 관리합니다.
- **`config/db_config.py`**: MongoDB 연결 및 데이터베이스 작업을 처리합니다.

## 사용법

1. 서버를 실행하면 설정된 간격(`INTERVAL`)으로 크롤링 작업이 수행됩니다.
2. 새로운 공지사항이 발견되면 데이터베이스에 저장됩니다.
3. 로그를 통해 크롤링 상태를 확인할 수 있습니다.

## 개발 및 테스트

- **테스트 환경**: 개발 환경에서는 `INTERVAL`이 짧게 설정되어 빠르게 테스트할 수 있습니다.
- **로깅**: 개발 환경에서는 DEBUG 레벨의 로그를 출력합니다.
## 스크래퍼 추가 및 dev 배포

새 게시판을 추가할 때의 전체 흐름입니다. 상세 지침은 `prompt/SCRAPER_CREATION_PROMPT.md` 참고.

### 1. 핸들러 작성

`lambda_web_scraper/{scraper_lambda_function_name에서 _scraper 제거}_handler.py`

- HTML 게시판: `university_academic_handler.py` 참고
- RSS 게시판: `dormitory_general_rss_handler.py` 참고
- DB에 저장하는 필드는 기존과 동일하게 `title` / `link` / `published`(ISO) / `scraper_type` 4개
- `link`가 상대경로거나 글 번호만 오는 경우가 있으므로 절대 URL로 변환할 것

### 2. 메타데이터 등록

`metadata/scraper_types.json`

```json
"GRADUATE_TOTALNOTICE_RSS": {
    "type_name": "GRADUATE_TOTALNOTICE_RSS",
    "korean_name": "대학원 전체공지",
    "url": "https://gds.kookmin.ac.kr/information/notice/rss",
    "scraper_class_name": "RSSNoticeScraper",
    "scraper_lambda_function_name": "graduate_totalnotice_rss_scraper"
}
```

`metadata/scraper_categories.json` — 기존 카테고리의 `scraper_types`에 타입명을 추가하거나, 새 카테고리를 만듭니다.

```json
"GRADUATE_CATEGORY": {
    "korean_name": "대학원",
    "scraper_types": ["GRADUATE_TOTALNOTICE_RSS"]
}
```

이름 규칙:

| 항목 | 규칙 | 예시 |
|---|---|---|
| 카테고리 | `{도메인}_CATEGORY` | `GRADUATE_CATEGORY` |
| 타입 | `{도메인}_{게시판}` (+RSS면 `_RSS`) | `GRADUATE_TOTALNOTICE_RSS` |
| 람다 함수 | 타입명 소문자 + `_scraper` | `graduate_totalnotice_rss_scraper` |
| 핸들러 파일 | 람다 함수명에서 `_scraper` → `_handler.py` | `graduate_totalnotice_rss_handler.py` |
| MongoDB 컬렉션 | 타입명 소문자 (자동 생성) | `graduate_totalnotice_rss` |

RSS 스크래퍼는 `scraper_class_name`을 공통으로 `RSSNoticeScraper`로 둡니다.

### 3. serverless.yml 함수 등록

`functions:` 아래, 컨테이너 이미지(🐳) 블록 위에 추가합니다.

```yaml
  # Graduate Total Notice RSS 스크래퍼
  graduate_totalnotice_rss_scraper:
    name: ${self:provider.stage}-graduate_totalnotice_rss_scraper
    handler: lambda_web_scraper.graduate_totalnotice_rss_handler.handler
    layers:
      - { Ref: ScraperDependenciesLambdaLayer }
```

### 4. 로컬 테스트

`.env`는 gitignore 대상이라 로컬에 직접 만들어야 합니다. `serverless-dotenv-plugin`이 이 파일을 읽어 Lambda 환경변수로 주입합니다.

```bash
cat > .env <<'ENVFILE'
MONGODB_URI=...
DB_NAME=dev-kookmin-feed
SLACK_BOT_TOKEN=...
SLACK_CHANNEL_ID=...
ENVFILE

npm ci
npx serverless invoke local -f graduate_totalnotice_rss_scraper --stage dev
```

- 전역 `sls`는 v4라 로그인을 요구합니다. `npx serverless`로 `package.json`에 고정된 v3를 쓰세요.
- 로컬 파이썬이 3.11이어야 합니다. `feedparser`가 3.13+에서 제거된 `cgi` 모듈에 의존합니다.
- 두 번 실행해서 두 번째에 `새로운 공지사항 수: 0`이 나오는지(중복 처리) 확인합니다.
- 확인이 끝나면 배포 환경에서 다시 테스트할 수 있도록 해당 컬렉션을 삭제합니다. 스크래핑 결과가 0건이면 컬렉션 자체가 생성되지 않는 점에 유의하세요.

### 5. 배포

| 대상 | 방법 |
|---|---|
| **dev** | 로컬에서 직접 배포 가능. `dev` 브랜치 push 시 GitHub Actions 자동 배포도 동작합니다. |
| **prod** | **반드시 Terraform Cloud를 통해서만.** `main` 브랜치에 push하면 트리거됩니다. 로컬에서 `--stage prod`로 배포하지 마세요. |

#### dev 로컬 배포

레이어는 **반드시 linux/amd64 컨테이너에서** 빌드해야 합니다. macOS에서 그냥 빌드하면 `aiohttp`, `pymongo`의 C 확장이 darwin 바이너리로 들어가 모든 람다가 임포트 단계에서 깨집니다.

```bash
mkdir -p layer/python
docker run --rm --platform linux/amd64 -v "$PWD":/w -w /w python:3.11-slim \
  sh -c "pip install -q -r requirements.txt -t layer/python"

npx serverless deploy --stage dev
```

`serverless.yml`은 `kookmin-feed` 프로필을 참조합니다. 로컬 프로필 이름이 다르면 `--aws-profile <name>`을 붙이세요.

배포 후 신규 함수가 실제로 동작하는지 원격 호출로 확인합니다.

```bash
npx serverless invoke -f graduate_totalnotice_rss_scraper --stage dev --log
```

### 6. 메타데이터 DB 동기화

**배포만으로는 디스코드 봇에 새 카테고리가 보이지 않습니다.** `metadata/*.json`을 MongoDB `scraper-metadata` DB에 반영하는 것은 master 람다이고, 개별 스크래퍼 람다는 메타데이터를 건드리지 않습니다.

```bash
npx serverless invoke -f master --stage dev --log
```

master는 실제로 배포된 람다 목록과 대조해 유효한 스크래퍼만 저장하므로, 3단계까지 마치고 배포한 뒤에 실행해야 합니다. 평소에는 EventBridge 스케줄(월~금 08:30~19:30 매시)로 자동 실행됩니다.

반영 경로:

```
metadata/*.json → (deploy) → master 람다 → MongoDB scraper-metadata
                                                    ↓
                                        데이터 API 서버 → 디스코드 봇
```

새 타입은 봇의 첫 주기에 최근 공지를 캐싱만 하고 알림을 보내지 않습니다. 실제 알림은 그다음 새 공지부터 발송됩니다.
