# Point

앱테크 출석/포인트 체크리스트 CLI. 자동 클릭(매크로) 없이, 오늘 할 일을 보여주고 직접 한 뒤 기록합니다.

```
python pointcli.py init                          # 조사한 기본 서비스 추가
python pointcli.py today                         # 오늘 할 일
python pointcli.py done 토스 --won 140           # 완료 기록 (--date YYYY-MM-DD 로 소급 가능)
python pointcli.py stats --days 30               # 수익 통계
python pointcli.py add 이름 --task 출석체크 --est 50 --expire-days 365 --note 메모
python pointcli.py edit 네이버페이 --expire-days 180   # 확인한 조건 반영
python pointcli.py expiring --within 30          # 30일 내 소멸 예정 적립금
python pointcli.py feed add https://.../rss      # 이벤트 RSS/Atom 피드 등록
python pointcli.py collect                       # 피드에서 이벤트 수집 (키워드: 출석/이벤트/포인트 등)
python pointcli.py events                        # 수집된 이벤트
python pointcli.py export-events                 # 앱용 app/events.json 생성
python pointcli.py morning [--telegram]         # 아침 리포트 한 번에 (수집+할 일+소멸 임박+새 이벤트)
python pointcli.py cron --at 08:00 [--telegram]  # 매일 자동 실행용 crontab 줄 출력
```

## 앱 (`app/`)
열면 **지금 시간에 열려 있는 항목**을 보여주는 설치형 웹 앱(PWA)입니다. 서버·계정 없이 동작하고 데이터는 기기(localStorage)에 저장됩니다.
- 지금 할 수 있는 것 / 오늘 곧 열리는 것 / 오늘 완료 / 새 이벤트 / 전체 항목
- 항목별 요일·시간대(자정 넘김 가능), 예상 수익, 링크 설정. 완료 시 받은 금액을 기록하고 이번 달 합계 표시
- 백업 내보내기/불러오기 (브라우저 데이터를 지우면 사라지므로 가끔 백업하세요)
- 시간대는 확인된 것만 설정했습니다(네이버페이 브랜드뽑기 14시). 나머지는 종일이니 앱에서 `수정`하세요.

실행: `cd app && python -m http.server 8000` 후 `http://localhost:8000` (PC) — 폰에서 쓰려면 `app/` 폴더를 GitHub Pages 등 HTTPS 정적 호스팅에 올리고 "홈 화면에 추가"하세요.
새 이벤트 목록: `python pointcli.py collect && python pointcli.py export-events`로 `app/events.json`을 만들면 앱에 표시됩니다(없어도 동작).

## GitHub Pages 배포 + 이벤트 자동 갱신
`.github/workflows/pages.yml`이 `app/`을 Pages로 배포하고, 6시간마다(UTC 기준 `17 */6 * * *`) 이벤트를 다시 수집해 `events.json`을 갱신합니다.
1. 이 워크플로를 `main`에 병합합니다 (예약 실행과 Pages 배포는 기본 브랜치에서만 동작).
2. 저장소 **Settings > Pages > Build and deployment > Source**를 **GitHub Actions**로 선택합니다.
3. **Actions** 탭에서 `Deploy app to GitHub Pages`를 `Run workflow`로 한 번 실행합니다.
4. 주소는 `https://<사용자>.github.io/<저장소>/` 입니다. 폰에서 열어 "홈 화면에 추가"하세요.

참고: 비공개 저장소의 Pages는 플랜에 따라 제한될 수 있습니다. 앱 코드를 고쳐 배포하면 설치한 폰에도 다음 접속 때 새 버전이 반영됩니다.

## 매일 아침 자동 실행
데이터(`~/.pointcli.db`)가 있는 **본인 컴퓨터/서버**에서 설정합니다.
1. `python pointcli.py init` 후 `python pointcli.py cron --at 08:00` 실행
2. 출력된 줄을 `crontab -e`에 붙여넣기 (결과는 `~/.pointcli.log`에 쌓임)
3. 폰으로 받으려면 텔레그램 봇을 만들어 `POINTCLI_TG_TOKEN`, `POINTCLI_TG_CHAT`을 crontab 상단에 설정하고 `--telegram` 사용

Windows는 작업 스케줄러에서 `python pointcli.py morning`을 매일 실행하도록 등록하세요.

- 기본 서비스 목록의 조건은 웹 검색 기반이며 **검증되지 않았습니다**. 앱 공지/약관을 확인해 `edit`로 고치세요.
- `expiring`은 유효기간(`--expire-days`)을 입력한 서비스만 계산합니다.
- `init`은 뽐뿌 `coupon`/`event` 피드도 등록합니다(열리고 robots.txt가 허용함을 확인). 개인용으로 가끔만 수집하세요.
- `collect`는 robots.txt가 막은 주소는 가져오지 않으며, 로그인이 필요한 페이지는 다루지 않습니다.
- 데이터: `~/.pointcli.db` (`POINTCLI_DB`로 변경). 테스트: `pytest`.
