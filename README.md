# SSU LMS 과제 알림

숭실대 LMS 마이페이지에서 과제를 수집하고, **설정한 마감 N시간 전**에 Discord로 알립니다.

## 동작 구상

1. **GitHub Actions** — 매시간 `main.py` 실행 → LMS 과제 수집  
2. **마감 임박** — 남은 시간이 `DUE_SOON_HOURS`(또는 Discord `/마감알림설정`) 이하인 과제만 웹훅 알림  
3. **중복 방지** — `due_soon_notified.json`으로 과제당 1회만 알림 (Actions 캐시로 유지)

## 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# .env: SSU_ID, SSU_PASSWORD, DISCORD_WEBHOOK_URL 등
python main.py
```

- 과제만 확인: `python get_token.py`  
- 웹훅 테스트: `python discord_bot.py`  
- 마감 시간 설정(슬래시 명령): `python discord_commands_bot.py` → Discord `/마감알림설정`

## GitHub Actions (1시간마다, PC 꺼져 있어도 실행)

### 1. GitHub에 코드 올리기

**본인 계정**이든 **팀원 계정**(`gimudowane-create/LMS-notice-bot` 등) 저장소든, push 권한만 있으면 동일합니다.

#### 처음 올릴 때 (PowerShell)

```powershell
cd "c:\Users\kkhoo\Desktop\2-2\Project"
git init
git add .

# 최초 1회: Git이 커밋 작성자를 알아야 합니다 (아래 이메일/이름은 본인 것으로 바꾸세요)
git config user.name "본인이름"
git config user.email "github에등록한이메일@example.com"

git commit -m "Add SSU LMS assignment checker with GitHub Actions"
git branch -M main

# 저장소가 없으면 추가 (이미 있으면 set-url 사용)
git remote add origin https://github.com/gimudowane-create/LMS-notice-bot.git
# 이미 origin이 다른 주소면:
# git remote set-url origin https://github.com/gimudowane-create/LMS-notice-bot.git

git push -u origin main
```

#### 자주 나는 에러

| 메시지 | 원인 | 해결 |
|--------|------|------|
| `Please tell me who you are` | `user.name` / `user.email` 미설정 | 위 `git config` 두 줄 실행 후 `git commit` 다시 |
| `src refspec main does not match any` | 커밋이 없음 (commit 실패) | `git commit` 성공 여부 확인 (`git log`) |
| `remote origin already exists` | remote 중복 | `git remote set-url origin https://github.com/...` |
| `Permission denied` / `403` | 팀 저장소 push 권한 없음 | 팀원이 Collaborator로 초대 |
| `Repository not found` | URL 오타 또는 비공개 repo 접근 불가 | URL·로그인 계정 확인 |

> README의 `<사용자명>`은 **예시**입니다. 그대로 붙여넣지 말고 실제 URL을 쓰세요.  
> 예: `https://github.com/gimudowane-create/LMS-notice-bot.git`

#### 팀원 계정 저장소에 올리는 경우

1. 팀원이 GitHub에서 `LMS-notice-bot` 저장소 생성 (또는 이미 생성됨)
2. 팀원이 **Settings → Collaborators** 에서 당신 GitHub 아이디를 **Write** 이상으로 초대
3. 당신 PC에서 `git push` (GitHub 로그인/토큰은 **push 하는 사람** 계정)
4. **Actions Secrets**(`SSU_ID`, `SSU_PASSWORD`)는 **그 저장소 Settings**에 등록  
   - 팀원이 등록해도 되고, 권한 있으면 당신이 등록해도 됨  
   - LMS 학번/비밀번호는 **누구 과제를 긁을지**에 맞게 정하면 됨 (본인/팀원 계정 모두 가능)

### 2. Secrets 등록

**코드가 올라간 그 저장소** → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 |
|-------------|-----|
| `SSU_ID` | 학번 |
| `SSU_PASSWORD` | 비밀번호 |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 URL (알림 채널) |
| `DUE_SOON_HOURS` | 마감 몇 시간 전 알림 (예: `24`) — `/마감알림설정`과 맞추기 |
| `DISCORD_GUILD_ID` | (선택) 서버 ID — 로컬에서 저장한 `lms_bot_settings.json`과 연동 시 |

`.env` 파일은 Git에 올리지 마세요. (`.gitignore`에 포함됨)

> Actions는 `python main.py`를 실행하며, **전체 과제 목록은 보내지 않고** 마감 임박 알림만 보냅니다.  
> Discord에서 `/마감알림설정`으로 12시간으로 바꿨다면, Secret `DUE_SOON_HOURS`도 `12`로 맞추세요.

### 3. 동작 확인

- **Actions** 탭 → **SSU LMS 과제 확인** → **Run workflow**
- 로그: `[마감 임박] 알림 기준: 마감 N시간 전` → 조건 맞는 과제만 Discord 전송
- 이후 **매시 정각** 자동 실행 (`cron: 0 * * * *`, UTC 기준)

> 같은 시각에 UTC·KST 모두 `:00`분입니다. 시계만 9시간 차이 납니다.  
> 예: UTC 00:00 = KST 09:00 (둘 다 정각)

### 4. 참고

- 무료 플랜도 시간당 1회 수준은 일반적으로 가능합니다.
- 60일 이상 저장소 활동이 없으면 GitHub가 scheduled workflow를 비활성화할 수 있습니다.
- SSO/캡차 정책이 바뀌면 Actions에서 로그인이 실패할 수 있습니다.

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SSU_ID` | 학번 | (필수) |
| `SSU_PASSWORD` | 비밀번호 | (필수) |
| `SSU_HEADLESS` | 브라우저 숨김 | `false` (Actions에서는 `true`) |
| `SSU_ONLY_ACTIVE_ASSIGNMENTS` | 마감 전 과제만 | `true` |
| `DISCORD_WEBHOOK_URL` | Discord 웹훅 | (필수, 알림 시) |
| `DUE_SOON_HOURS` | 마감 N시간 전 알림 | `24` |
| `SSU_SEND_ALL_ASSIGNMENTS` | 수집 시 전 과제 전송 | `true` (Actions는 `false`) |
| `SSU_TIMEZONE` | 마감 시각 기준 | `Asia/Seoul` |
