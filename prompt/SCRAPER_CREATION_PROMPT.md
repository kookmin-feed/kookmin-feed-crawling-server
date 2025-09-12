# Kookmin Feed 웹 스크래퍼 생성 프롬프트

## 최우선으로 수행할 것
- `pyenv init && pyenv shell 3.11.5` 명령어를 수행하여 pyenv shell 환경에서 작업하라. 이것이 안되면 실행을 중지하라.

## 프롬프트 입력 형식

```
url: @{target_url}
엘리먼트: @{example_html_file}
scraper_category: {CATEGORY_NAME}
scraper_type: {SCRAPER_TYPE_NAME}
```

## 프롬프트 내용

```
1. @university_academic_handler.py 의 구조를 참고하여 lambda_web_scraper/ 안에 lambda function을 만들라. 이 lambda function의 역할은 주어진 url에서 공지사항을 스크래핑하고, 새로운 공지사항을 처리하는 것이다.
2. 스크래퍼 카테고리와 스크래퍼 타입을 반영하여 metadata/ 안의 json들을 적절히 수정하라.
3. 이 내용을 @serverless.yml 에 반영하라.
4. sls invoke local -f {스크래퍼명} --stage dev 명령어를 실행하여 로컬 환경에서 함수가 잘 동작하는 지 테스트한다.
5. mongoDB를 조회하여 해당 스크래퍼에 대한 컬렉션이 잘 생성되었는지 확인한다. 이때 스크래핑된 공지가 0개일 때는 컬렉션이 생성되지 않으므로 이를 유념한다.
6. 이 명령어를 한 번 더 테스트하여 로컬 환경에서 중복된 공지에 대한 핸들링이 잘 되는지 테스트한다.
7. 이 과정이 끝나면 추후 배포 환경에서의 원활한 테스트를 위하여 DB에서 해당 컬렉션을 삭제한다.
8. 모든 것이 완벽하다면 이를 dev 브랜치에 push 한다.
```

## 참고사항
- 만약 스크래핑된 공지가 0개일 때는 컬렉션이 생성되지 않으므로 이를 유념한다.
- 새로운 카테고리를 만들어야한다면, metadata/scraper_categories.json 에 카테고리를 추가하라. 이때의 korean_name 필드는 프롬프트로 제공해주겠다.