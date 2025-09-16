### 입력값

```
url: {url}
example_html_file: {example_html_file}
scraper_type_name: {scraper_type_name}
scraper_type_korean_name: {scraper_type_korean_name}
scraper_class_name: {scraper_class_name}
scraper_lambda_function_name: {scraper_lambda_function_name}
scraper_category_name: {scraper_category_name}
scraper_category_korean_name: {scraper_category_korean_name}
```

### 수행 절차

1. {url}에 대해 @library_general_handler.py의 구조를 차용하여 playwright를 활용한 동적 웹페이지 스크래핑 람다 펑션을 만들어라. 이때 파싱 대상이 되는 엘리먼트는 @example.html를 참고하라. 특히 DB에 저장되는 notice 형식은 기존의 것을 반드시 준용하라.

2. 아래 내용으로 @scraper_types.json  을 업데이트 하라. 

    "{scraper_type_name}": {
        "type_name": "{scraper_type_name}",
        "korean_name": "{scraper_type_korean_name}",
        "url": "{url}",
        "scraper_class_name": "{scraper_class_name}",
        "scraper_lambda_function_name": "{scraper_lambda_function_name}"
    }

3. 아래 내용으로 @scraper_categories.json를 업데이트 하라.

    "{scraper_category_name}": {
        "korean_name": "{scraper_category_korean_name}",
        "scraper_types": [
            "{scraper_type_name}"
        ]
    }

4. 멀티 스테이지 빌드에 맞게 @Dockerfile를 수정하고, @serverless.yml을 적절히 수정하라. 

5. @build-images.sh 로 빌드해보고 @DOCKER_BUILD_AND_TEST_GUIDE.md 를 참고하여 로컬 테스트를 수행하라. 이때 docker logs 명령을 수행하지 마라.