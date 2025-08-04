import json
import boto3
import os
from pymongo import MongoClient


def handler(event, context):
    """
    Master Lambda Handler
    EventBridge에서 호출되어 유효한 스크래퍼 Lambda 함수들을 비동기로 실행하는 진입점
    """

    try:
        print("🚀 [MASTER] Master Handler 시작")

        # 1. JSON 파일들 로드
        print("📋 [MASTER] 스크래퍼 설정 파일 로드")
        scraper_types = load_scraper_types()
        scraper_categories = load_scraper_categories()

        if not scraper_types or not scraper_categories:
            print("❌ [MASTER] 스크래퍼 설정 파일 로드 실패")
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {"error": "스크래퍼 설정 파일을 로드할 수 없습니다."},
                    ensure_ascii=False,
                ),
            }

        print(f"📊 [MASTER] 로드된 스크래퍼 타입: {len(scraper_types)}개")
        print(f"📊 [MASTER] 로드된 스크래퍼 카테고리: {len(scraper_categories)}개")

        # 2. Lambda 클라이언트 생성
        lambda_client = boto3.client("lambda")

        # 3. 모든 Lambda 함수 목록 가져오기
        print("🔍 [MASTER] Lambda 함수 목록 조회")
        response = lambda_client.list_functions()
        all_functions = response["Functions"]

        # 추가 페이지가 있는 경우 계속 가져오기
        while "NextMarker" in response:
            response = lambda_client.list_functions(Marker=response["NextMarker"])
            all_functions.extend(response["Functions"])

        # 4. scraper로 끝나는 함수들만 필터링
        scraper_functions = [
            func["FunctionName"]
            for func in all_functions
            if func["FunctionName"].endswith("scraper")
        ]

        print(f"📋 [MASTER] 발견된 스크래퍼 Lambda 함수: {len(scraper_functions)}개")

        # 5. 유효한 스크래퍼 함수들 필터링
        valid_scrapers = validate_scrapers(
            scraper_functions, scraper_types, scraper_categories
        )

        print(f"✅ [MASTER] 유효한 스크래퍼: {len(valid_scrapers)}개")
        print(
            f"❌ [MASTER] 유효하지 않은 스크래퍼: {len(scraper_functions) - len(valid_scrapers)}개"
        )

        # 6. 유효한 스크래퍼 정보를 DB에 저장
        print("💾 [MASTER] 스크래퍼 메타데이터 DB 저장 시작")
        save_scraper_categories_to_db(scraper_categories)
        save_scraper_types_to_db(scraper_types, valid_scrapers)
        print("💾 [MASTER] 스크래퍼 메타데이터 DB 저장 완료")

        success_count = 0
        error_count = 0
        invocation_results = []

        # 6. 유효한 스크래퍼 함수들만 비동기로 호출
        for function_name in valid_scrapers:
            try:
                # 개별 스크래퍼 Lambda 함수 비동기 호출
                lambda_client.invoke(
                    FunctionName=function_name,
                    InvocationType="Event",  # 비동기 호출
                    Payload=json.dumps({}),
                )

                success_count += 1
                invocation_results.append(
                    {
                        "function_name": function_name,
                        "status": "success",
                        "message": "비동기 호출 성공",
                    }
                )

            except Exception as e:
                error_count += 1
                invocation_results.append(
                    {
                        "function_name": function_name,
                        "status": "error",
                        "message": str(e),
                    }
                )

        result = {
            "message": "Master Lambda Handler 실행 완료",
            "validation": {
                "total_found": len(scraper_functions),
                "valid_scrapers": len(valid_scrapers),
                "invalid_scrapers": len(scraper_functions) - len(valid_scrapers),
                "valid_scraper_functions": valid_scrapers,
            },
            "invocation": {
                "total_scrapers": len(valid_scrapers),
                "invoked_successfully": success_count,
                "invocation_failed": error_count,
                "invocation_results": invocation_results,
            },
        }

        print(f"🎉 [MASTER] 실행 완료 - 성공: {success_count}, 실패: {error_count}")
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False, default=str),
        }

    except Exception as e:
        print(f"❌ [MASTER] Master Handler 실행 중 오류: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Master Lambda Handler 실행 중 오류가 발생했습니다.",
                    "details": str(e),
                },
                ensure_ascii=False,
            ),
        }


def load_scraper_types():
    """스크래퍼 타입 JSON 파일을 로드합니다."""
    try:
        with open("metadata/scraper_types.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scraper_types", {})
    except Exception as e:
        print(f"❌ [LOAD] 스크래퍼 타입 파일 로드 실패: {e}")
        return {}


def load_scraper_categories():
    """스크래퍼 카테고리 JSON 파일을 로드합니다."""
    try:
        with open("metadata/scraper_categories.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("scraper_categories", {})
    except Exception as e:
        print(f"❌ [LOAD] 스크래퍼 카테고리 파일 로드 실패: {e}")
        return {}


def validate_scrapers(scraper_functions, scraper_types, scraper_categories):
    """
    스크래퍼 Lambda 함수들이 유효한지 검증합니다.

    Args:
        scraper_functions: Lambda 함수 이름 리스트
        scraper_types: 스크래퍼 타입 정보
        scraper_categories: 스크래퍼 카테고리 정보

    Returns:
        List[str]: 유효한 스크래퍼 Lambda 함수 이름 리스트
    """
    valid_scrapers = []

    # JSON에 정의된 스크래퍼 타입들을 순회하면서 해당하는 Lambda 함수가 존재하는지 확인
    for scraper_type, scraper_info in scraper_types.items():
        # 1. 스크래퍼 타입이 어떤 카테고리에 속하는지 확인
        category = find_category_by_scraper_type(scraper_type, scraper_categories)
        if not category:
            print(
                f"❌ [VALIDATE] 카테고리를 찾을 수 없는 스크래퍼 타입: {scraper_type}"
            )
            continue

        # 3. JSON의 scraper_lambda_function_name과 실제 Lambda 함수명을 직접 비교
        expected_function_name = scraper_info.get("scraper_lambda_function_name")
        if not expected_function_name:
            print(
                f"❌ [VALIDATE] Lambda 함수명이 정의되지 않은 스크래퍼 타입: {scraper_type}"
            )
            continue

        # 실제 Lambda 함수 이름 생성 (환경별 접두사 포함)
        actual_function_names = generate_actual_function_names(expected_function_name)

        # 실제 존재하는 Lambda 함수 찾기
        matching_function = None
        for actual_name in actual_function_names:
            if actual_name in scraper_functions:
                matching_function = actual_name
                break

        if not matching_function:
            print(
                f"❌ [VALIDATE] Lambda 함수가 존재하지 않는 스크래퍼 타입: {scraper_type} (예상: {expected_function_name})"
            )
            continue

        print(
            f"✅ [VALIDATE] 유효한 스크래퍼: {matching_function} ({scraper_type} -> {category})"
        )
        valid_scrapers.append(matching_function)

    return valid_scrapers


def generate_actual_function_names(expected_function_name):
    """
    예상되는 Lambda 함수명으로부터 실제 Lambda 함수명들을 생성합니다.

    Args:
        expected_function_name: 예상되는 함수명 (예: university_academic_scraper)

    Returns:
        List[str]: 실제 Lambda 함수명 리스트
    """
    # prefix 없이 직접 비교하므로 예상 함수명 그대로 반환
    return [expected_function_name]


def find_category_by_scraper_type(scraper_type, scraper_categories):
    """
    스크래퍼 타입이 속한 카테고리를 찾습니다.

    Args:
        scraper_type: 스크래퍼 타입
        scraper_categories: 스크래퍼 카테고리 정보

    Returns:
        str: 카테고리 이름 또는 None
    """
    for category_name, category_info in scraper_categories.items():
        if scraper_type in category_info.get("scraper_types", []):
            return category_name
    return None


def get_database(db_name: str = None):
    """MongoDB 데이터베이스 연결을 반환합니다."""
    try:
        mongodb_uri = os.environ.get("MONGODB_URI")
        if not mongodb_uri:
            print("❌ [DB] MongoDB URI가 설정되지 않았습니다")
            return None

        client = MongoClient(mongodb_uri)
        default_db = "dev-kookmin-feed"
        db_name = db_name or os.environ.get("DB_NAME") or default_db
        return client[db_name]
    except Exception as e:
        print(f"❌ [DB] DB 연결 중 오류 발생: {e}")
        return None


def get_collection(db_name: str = None, collection_name: str = None):
    """DB내 컬렉션 반환."""
    db = get_database(db_name)
    if db is None:
        return None
    return db[collection_name]


def save_scraper_categories_to_db(scraper_categories):
    """ScraperCategory 데이터를 DB에 저장합니다."""
    try:
        collection = get_collection(
            db_name="scraper-metadata", collection_name="scraper-categories"
        )
        if collection is None:
            print("❌ [DB] 컬렉션을 가져올 수 없습니다")
            return False

        for category_name, category_info in scraper_categories.items():
            collection.update_one(
                {"name": category_name},
                {
                    "$set": {
                        "korean_name": category_info.get("korean_name", ""),
                        "scraper_type_names": category_info.get("scraper_types", []),
                    }
                },
                upsert=True,
            )
        print("✅ [DB] ScraperCategory 저장 또는 업데이트 완료")
        return True
    except Exception as e:
        print(f"❌ [DB] ScraperCategory 저장 또는 업데이트 중 오류 발생: {e}")
        return False


def save_scraper_types_to_db(scraper_types, valid_scrapers):
    """유효한 스크래퍼 타입들을 DB에 저장합니다."""
    try:
        collection = get_collection(
            db_name="scraper-metadata", collection_name="scraper-types"
        )
        if collection is None:
            print("❌ [DB] 컬렉션을 가져올 수 없습니다")
            return False

        saved_count = 0
        for scraper_type, scraper_info in scraper_types.items():
            # 유효한 스크래퍼만 저장
            if scraper_info.get("scraper_lambda_function_name") in valid_scrapers:
                collection.update_one(
                    {"collection_name": scraper_type},
                    {
                        "$set": {
                            "type_name": scraper_type,
                            "korean_name": scraper_info.get("korean_name", ""),
                            "url": scraper_info.get("url", ""),
                            "scraper_class_name": scraper_info.get(
                                "scraper_class_name", ""
                            ),
                            "scraper_lambda_function_name": scraper_info.get(
                                "scraper_lambda_function_name", ""
                            ),
                        }
                    },
                    upsert=True,
                )
                saved_count += 1
                print(
                    f"✅ [DB] ScraperType 저장: {scraper_info.get('korean_name', '')}"
                )

        print(f"✅ [DB] ScraperType 저장 또는 업데이트 완료: {saved_count}개")
        return True
    except Exception as e:
        print(f"❌ [DB] ScraperType 저장 또는 업데이트 중 오류 발생: {e}")
        return False
