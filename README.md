# SSU LMS 과제 알림봇

숭실대학교 LMS에서 과제를 자동으로 수집하고, **마감 시간이 임박하면 Discord로 알림**을 보내는 자동화 봇입니다.

## 🎯 주요 기능

- **자동 과제 수집**: Playwright를 이용한 LMS 크롤링 (매시간 실행)
- **마감 임박 알림**: 설정된 시간(기본 24시간) 전부터 Discord로 알림
- **중복 알림 방지**: 같은 과제는 한 번만 알림
- **서버별 설정**: Discord 슬래시 명령으로 서버마다 다른 알림 시간 설정 가능
- **GitHub Actions 자동화**: 클라우드에서 매시간 자동 실행 (PC 켜져있지 않아도 됨)

---

## 🔄 동작 흐름

### 1단계: LMS 로그인 & 과제 수집 (`get_token.py`)

```
LMS 홈페이지 → "통합 로그인" 버튼 클릭
    ↓
SmartID SSO 인증 (학번/비밀번호 제출)
    ↓
마이페이지 접속 → iframe 로드
    ↓
"모두 펼치기" 버튼 클릭 → 과제 목록 파싱
    ↓
과제 정보 추출 (과목명, 제목, 마감시간, 링크)
```

**세부 기술:**
- **Playwright**: Chromium 기반 브라우저 자동화
- **스텔스 모드**: 자동화 감지 회피 (`navigator.webdriver` 속성 제거, 크로스 오리진 보안 정책 우회)
- **재시도 로직**: iframe 로드 실패 시 최대 2회 재시도
- **타임존 보정**: GitHub Actions (UTC) 환경에서 자동으로 KST(한국 시간)로 변환

### 2단계: 마감 임박 과제 필터링 (`due_soon_notify.py`)

```
수집된 과제 목록
    ↓
"마감이 아직 안 지났는가?" 확인
    ↓
"마감까지 설정된 시간(기본 24시간) 이내인가?" 확인
    ↓
이미 알린 과제는 건너뛰기 (due_soon_notified.json 확인)
    ↓
마감 임박 과제만 선별
```

**상태 관리:**
- `due_soon_notified.json`: 이미 알린 과제 키 저장
- 과제 마감 후 자동으로 상태에서 제거
- 중복 알림 완벽 차단

### 3단계: Discord 알림 전송 (`discord_bot.py`)

```
마감 임박 과제 정보
    ↓
Discord Embed 형식으로 변환
    ├─ 색상: 주황색 (마감 임박 표시)
    ├─ 제목: 과제명
    ├─ 내용: 과목명, 마감 시간, 남은 시간
    └─ 링크: LMS 과제 상세 페이지
    ↓
Discord 웹훅 API로 전송
```

**예시 알림:**
```
⏰ 과제 마감 24시간 이내!

[제목] 네트워크 프로그래밍 과제 3
[과목] 네트워크 프로그래밍
[마감] 2026.06.10 23:59
[남은 시간] 약 23시간 45분
```

### 4단계: 설정 관리 (`bot_settings.py`, `discord_commands_bot.py`)

Discord 슬래시 명령으로 실시간 설정 변경:

```
/마감알림설정 [시간]     → 마감 N시간 전 알림 설정 (1~168시간)
/마감알림확인           → 현재 설정 확인
```

**설정 우선순위:**
1. Discord 명령어로 저장한 **서버별 설정** (lms_bot_settings.json)
2. GitHub Secrets `DUE_SOON_HOURS`
3. 환경변수 `.env` 파일
4. 기본값: 24시간

---

## 🚀 실행 방법

### 로컬 실행

#### 사전 준비

```bash
# 1. Python 패키지 설치
pip install -r requirements.txt

# 2. Playwright 브라우저 설치
python -m playwright install chromium

# 3. 환경 변수 설정
cp .env.example .env
# .env 파일 편집: SSU_ID, SSU_PASSWORD, DISCORD_WEBHOOK_URL 등
```

#### 실행 명령어

```bash
# 메인 프로그램 (과제 수집 + 마감 임박 알림)
python main.py

# Discord 봇 (슬래시 명령어 서버)
python discord_commands_bot.py

# 과제만 확인 (알림 없이)
python get_token.py

# 웹훅 연결 테스트
python discord_bot.py

# 마감 임박 알림 테스트
python discord_bot.py due_soon
```

### GitHub Actions 자동 실행

#### 1단계: 저장소 생성 및 코드 푸시

**첫 번째 푸시 (PowerShell)**
```powershell
cd "c:\Users\kkhoo\Desktop\2-2\Project"
git init
git add .
git config user.name "본인이름"
git config user.email "github@example.com"
git commit -m "Initial commit: SSU LMS assignment notifier"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

#### 2단계: GitHub Secrets 등록

저장소 → Settings → Secrets and variables → Actions → New repository secret

| 항목 | 값 |
|------|-----|
| `SSU_ID` | 숭실대 학번 |
| `SSU_PASSWORD` | LMS 비밀번호 |
| `DISCORD_WEBHOOK_URL` | [Discord 웹훅 URL 생성법](#discord-웹훅-url-생성) |
| `DUE_SOON_HOURS` | 마감 몇 시간 전 알림 (예: 24) |
| `DISCORD_GUILD_ID` | (선택) Discord 서버 ID - 로컬 설정과 동기화 시 필요 |

#### 3단계: 동작 확인

저장소 → Actions 탭 → "SSU LMS 과제 확인" → Run workflow

**매시간 자동 실행:** UTC 매 정각 (= KST 09:00, 10:00, ... 매시간)

---

## 📋 환경 변수

### 필수 항목

| 변수 | 설명 |
|------|-----|
| `SSU_ID` | 숭실대 학번 |
| `SSU_PASSWORD` | LMS 비밀번호 |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 URL (알림 전송) |

### 선택 항목

| 변수 | 기본값 | 설명 |
|------|--------|-----|
| `DUE_SOON_HOURS` | 24 | 마감 N시간 전 알림 |
| `SSU_HEADLESS` | false | 브라우저 창 숨김 (GitHub Actions는 true) |
| `SSU_KEEP_BROWSER_OPEN` | true | 로컬: 로그인 실패 시 브라우저 유지 |
| `SSU_ONLY_ACTIVE_ASSIGNMENTS` | true | 마감 지난 과제 제외 |
| `SSU_SEND_ALL_ASSIGNMENTS` | false | 전체 과제 Discord 전송 (마감 임박만 아님) |
| `SSU_TIMEZONE` | Asia/Seoul | 마감 시간 기준 타임존 |
| `SSU_DEBUG` | false | 디버그 모드: 스크린샷 저장 |
| `DISCORD_BOT_TOKEN` | - | Discord 봇 명령어 사용 시 필요 |
| `DISCORD_GUILD_ID` | - | 특정 서버에만 명령어 활성화 |

---

## 🔐 Discord 웹훅 URL 생성

1. Discord 서버 → 채널 우클릭 → 채널 편집
2. 통합 → 웹훅 → 새 웹훅 생성
3. 웹훅 이름 설정 (예: "LMS 알림")
4. "웹훅 URL 복사" → `.env` 파일에 `DISCORD_WEBHOOK_URL` 값으로 저장

---

## ⚠️ 자주 나는 문제

| 증상 | 원인 | 해결 |
|------|------|-----|
| `로그인 실패` | 아이디/비밀번호 오류 | 숭실대 포탈에서 직접 로그인 확인 |
| `SSO 완료 대기 시간 초과` | 캡차/2차 인증 필요 | 로컬에서 먼저 수동 로그인 테스트 |
| `iframe 로드 실패` | 네트워크 지연 | GitHub Actions 재실행 또는 재시도 로직 발동 |
| `Permission denied / 403` | GitHub push 권한 없음 | Collaborator로 초대 또는 본인 저장소 사용 |
| `과제가 수집되지 않음` | LMS 구조 변경 또는 셀렉터 오류 | `SSU_DEBUG=true` 로 스크린샷 확인 |

---

## 📁 주요 파일 설명

```
Project/
├── main.py                    # 메인 진입점 (과제 수집 + 알림)
├── get_token.py              # LMS 크롤링 (Playwright)
├── due_soon_notify.py         # 마감 임박 필터링 및 상태 관리
├── discord_bot.py             # Discord 웹훅 API
├── discord_commands_bot.py    # Discord 슬래시 명령어 봇
├── bot_settings.py            # 설정 저장/조회
├── lms_time.py                # 타임존 및 시간 유틸
├── due_soon_notified.json     # 이미 알린 과제 상태 (자동 생성)
├── lms_bot_settings.json      # Discord 명령어로 저장한 설정
├── .env                       # 환경 변수 (Git 제외)
├── .env.example               # 환경 변수 템플릿
├── requirements.txt           # Python 패키지 의존성
└── .github/workflows/         # GitHub Actions 설정
    └── check_lms.yml          # 매시간 실행 워크플로우
```

---

## 🛠️ 개발 참고

### 로컬 테스트 팁

```bash
# 1. 스텔스 모드 확인 (자동화 감지 안 됨)
SSU_DEBUG=true python get_token.py

# 2. 디버그 스크린샷 확인
# → ssu_lms_debug/ 디렉토리 생성됨

# 3. 마감 임박 알림 테스트
python discord_bot.py due_soon

# 4. 특정 시간대만 테스트
DUE_SOON_HOURS=1 python main.py
```

### 코드 변경 시 주의사항

- **LMS 마이페이지 구조 변경**: CSS 클래스 선택자 업데이트 필요
  - 과제 컨테이너: `.xn-student-course-container`
  - 과제 아이템: `.xn-student-todo-item-container`
  - iframe: `#fulliframe`

- **SmartID 로그인 흐름 변경**: `login_lms()` 함수 재검토
  - SSO 완료 대기: `wait_for_sso_completion()`
  - pFrame 모니터링: SmartID의 숨겨진 iframe 감지

---

## 📜 라이센스

이 프로젝트는 개인 학습 및 과제 관리용입니다.

---

## 📞 문제 해결

**GitHub Actions에서 실패한 경우:**
1. Actions 탭 → 실패한 워크플로우 → 로그 확인
2. 로그 메시지 기반으로 위 "자주 나는 문제" 표 참고
3. `SSU_DEBUG=true`로 GitHub Secret 추가하면 스크린샷 저장 (Actions 아티팩트에서 확인 가능)

**로컬에서 재현 불가한 경우:**
- GitHub Actions 환경: Headless 모드, UTC 타임존
- 로컬 환경: GUI 모드, Asia/Seoul 타임존
- 시차 보정 로직 확인: `_adjust_utc_to_kst_string()`
