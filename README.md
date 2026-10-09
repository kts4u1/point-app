# Point

앱테크 출석/이벤트 체크 도구. **자동으로 눌러주지 않습니다.** 지금 할 수 있는 것을 보여주고, 직접 한 뒤 완료만 기록합니다.
(매크로·자동 클릭은 약관 위반과 계정 정지 위험이 있어 의도적으로 제외했습니다.)

**앱: https://kts4u1.github.io/point-app/** — 폰에서 열고 "홈 화면에 추가"하세요.

## 앱 (`app/`)
서버·계정 없이 동작하는 설치형 웹 앱(PWA)입니다. 데이터는 기기(localStorage)에만 저장됩니다.

- **지금 할 수 있는 것 / 곧 열려요 / 오늘 완료**를 현재 시각 기준으로 보여줍니다. 항목마다 요일·시간대(자정 넘김 가능), 예상 수익, 링크를 설정합니다.
- **바로 열기**: 항목에 주소가 있으면 `열기` 버튼으로 해당 페이지/앱을 열고, 돌아오면 "했나요?"라고 물어봅니다. `완료`를 누르고 받은 금액을 입력하면 이번 달 합계가 쌓입니다.
- **이벤트 고르기**: 앱테크에 도움이 되는 말(출석·퀴즈·뽑기·네이버페이·토스·포인트 등)이 든 글을 점수 순으로 보여주고, 분류 칩(출석·퀴즈·뽑기 / 네이버페이 / 토스 / 쿠폰·상품권)과 검색, `숨기기`, `더 보기`, `내 항목으로 추가`를 지원합니다. 제목에서 마감일(`~7/30`, `7.20~7.31`)을 찾아 지난 것은 기본으로 숨깁니다.
- 폰과 PC는 연동되지 않습니다. 브라우저 데이터를 지우면 사라지니 가끔 **백업 내보내기**를 하세요.
- 기본 항목의 적립 조건은 웹 검색 기반이며 **검증되지 않았습니다.** 시간대는 확인된 것만 설정했습니다(네이버페이 브랜드뽑기 14시). 나머지는 종일이니 앱의 `수정`으로 실제 조건에 맞추세요.

### 앱 연결(열기 주소)에 대해
- 토스·네이버페이 같은 앱의 **계정과 연결해 출석 여부를 자동으로 읽어오지는 않습니다.** 공개 API가 없고, 로그인 정보를 다루거나 화면을 긁는 방식은 약관 위반과 계정 정지 위험이 있어 의도적으로 제외했습니다.
- 대신 항목의 `열기 주소`로 연결합니다. 웹 주소(`https://…`)는 항상 열립니다. 앱을 바로 여는 주소(`앱이름://…`)는 앱마다 달라서, **토스·캐시워크 등은 공식 주소를 확인하지 못해 비워 뒀습니다.** 확인한 주소를 `수정`에서 직접 넣으세요.
- 네이버페이 항목에는 커뮤니티가 공유한 웹 주소(`point.pay.naver.com/…`)를 넣어 뒀습니다. 열면 로그인 화면을 거치며, 공식 문서로 확인한 주소는 아닙니다.
- `javascript:` 같은 위험한 주소는 저장·표시되지 않으며, 이벤트 링크는 `http(s)`만 허용합니다.

## 새 이벤트 자동 갱신
`.github/workflows/pages.yml`이 6시간마다(UTC `17 */6 * * *`) 피드에서 이벤트를 수집해 `app/events.json`을 만들고 Pages에 배포합니다. `main`에 `app/`, `pointcli.py`, `feeds.txt`, 워크플로가 푸시될 때와 Actions 탭의 `Run workflow`로도 실행됩니다.

- **누적**: 매번 이전 배포의 `events.json`을 받아 합칩니다(링크 기준 중복 제거, 최대 500건, 90일 지난 것은 삭제). 피드가 한 번에 15건만 주기 때문에, 시간이 지날수록 목록이 쌓입니다. 처음엔 적고 며칠 지나면 늘어납니다.
- **출처 추가**: 저장소의 `feeds.txt`에 `URL 이름`을 한 줄 추가하면 다음 갱신부터 반영됩니다(GitHub 웹에서 편집 가능). 기본 출처는 뽐뿌 쿠폰·이벤트·재테크 게시판입니다.
- 뽐뿌 글은 사용자가 올린 것이라 링크를 열기 전에 출처를 확인하세요.
- 수집은 robots.txt가 허용하는 공개 피드만 대상으로 하며, 개인용으로 낮은 빈도로만 사용하세요. 구글 뉴스 RSS 등은 robots.txt가 막아 쓰지 않습니다.
- 저장소에 한 달 정도 활동이 없으면 GitHub가 예약 실행을 멈출 수 있습니다. 그때는 Actions 탭에서 다시 켜세요.

## CLI (선택): `pointcli.py`
컴퓨터에서 쓰는 터미널 버전입니다. Python 3와 표준 라이브러리만 필요합니다. 데이터는 `~/.pointcli.db`(`POINTCLI_DB`로 변경)에 저장됩니다.

```
python pointcli.py init                          # 기본 서비스·피드 등록
python pointcli.py today                         # 오늘 할 일
python pointcli.py done 토스 --won 140           # 완료 기록 (--date YYYY-MM-DD 로 소급)
python pointcli.py stats --days 30               # 수익 통계
python pointcli.py add 이름 --task 출석체크 --est 50 --expire-days 365 --note 메모
python pointcli.py edit 네이버페이 --expire-days 180   # 확인한 조건 반영
python pointcli.py expiring --within 30          # 30일 내 소멸 예정 적립금
python pointcli.py feed add https://.../rss --label 이름   # RSS/Atom 피드 등록 (feeds.txt로도 가능)
python pointcli.py collect                       # 이벤트 수집 (키워드: 출석/이벤트/포인트 등)
python pointcli.py events                        # 수집된 이벤트
python pointcli.py export-events [--merge 기존.json]   # app/events.json 생성 (--merge로 누적)
python pointcli.py morning [--telegram]          # 수집+할 일+소멸 임박+새 이벤트 리포트
python pointcli.py cron --at 08:00 [--telegram]  # 매일 실행용 crontab 줄 출력
```

- `expiring`은 유효기간(`--expire-days`)을 입력한 서비스만 계산합니다.
- `collect`는 robots.txt가 막은 주소나 로그인이 필요한 페이지는 가져오지 않습니다.
- 매일 아침 자동 실행: `cron` 출력 줄을 `crontab -e`에 붙여넣으세요. Windows는 작업 스케줄러에서 `python pointcli.py morning`을 매일 실행하도록 등록합니다.
- 텔레그램 전송(`--telegram`)은 `POINTCLI_TG_TOKEN`, `POINTCLI_TG_CHAT` 환경변수가 필요합니다. 아직 실제 전송을 시험하지 못했습니다.

## 개발
```
python -m pytest -q                  # CLI 테스트
cd app && python -m http.server 8000 # 앱 로컬 실행 (http://localhost:8000)
```
앱을 고쳐 배포하면 서비스 워커가 네트워크 우선이라 설치한 폰에도 다음 접속 때 새 버전이 반영됩니다.
