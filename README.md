# Point

앱테크 출석/이벤트 체크 도구. **자동으로 눌러주지 않습니다.** 지금 할 수 있는 것을 보여주고, 직접 한 뒤 완료만 기록합니다.
(매크로·자동 클릭은 약관 위반과 계정 정지 위험이 있어 의도적으로 제외했습니다.)

**앱: https://kts4u1.github.io/point-app/** — 폰에서 열고 "홈 화면에 추가"하세요.

## 앱 (`app/`)
서버·계정 없이 동작하는 설치형 웹 앱(PWA)입니다. 데이터는 기기(localStorage)에만 저장됩니다.

- **지금 할 수 있는 것 / 곧 열려요 / 오늘 완료 / 새 이벤트 / 전체 항목**을 현재 시각 기준으로 보여줍니다.
- 항목마다 요일·시간대(자정 넘김 가능), 예상 수익, 링크를 설정합니다.
- `완료`를 누르고 받은 금액을 입력하면 이번 달 합계가 쌓입니다.
- 폰과 PC는 연동되지 않습니다. 브라우저 데이터를 지우면 사라지니 가끔 **백업 내보내기**를 하세요.
- 기본 항목의 적립 조건은 웹 검색 기반이며 **검증되지 않았습니다.** 시간대는 확인된 것만 설정했습니다(네이버페이 브랜드뽑기 14시). 나머지는 종일이니 앱의 `수정`으로 실제 조건에 맞추세요.

## 새 이벤트 자동 갱신
`.github/workflows/pages.yml`이 6시간마다(UTC `17 */6 * * *`) 뽐뿌 `coupon`/`event` 피드에서 이벤트를 수집해 `app/events.json`을 만들고 Pages에 배포합니다. `main`에 `app/`, `pointcli.py`, 워크플로가 푸시될 때와 Actions 탭의 `Run workflow`로도 실행됩니다.

- 뽐뿌 글은 사용자가 올린 것이라 링크를 열기 전에 출처를 확인하세요.
- 수집은 robots.txt가 허용하는 공개 피드만 대상으로 하며, 개인용으로 낮은 빈도로만 사용하세요.
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
python pointcli.py feed add https://.../rss      # RSS/Atom 피드 등록
python pointcli.py collect                       # 이벤트 수집 (키워드: 출석/이벤트/포인트 등)
python pointcli.py events                        # 수집된 이벤트
python pointcli.py export-events                 # app/events.json 생성
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
