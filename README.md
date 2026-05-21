# SSU LMS 과제 수집

숭실대 LMS 마이페이지에서 진행 중인 과제를 자동으로 수집합니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# .env 에 SSU_ID, SSU_PASSWORD 입력
python get_token.py
```

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
| `SSU_ID` | 학번 (`.env`의 `SSU_ID`) |
| `SSU_PASSWORD` | 비밀번호 (`.env`의 `SSU_PASSWORD`) |

`.env` 파일은 Git에 올리지 마세요. (`.gitignore`에 포함됨)

### 3. 동작 확인

- **Actions** 탭 → **SSU LMS 과제 확인** 워크플로 선택
- **Run workflow** 로 수동 실행해 본 뒤, 로그에 과제 목록이 나오는지 확인
- 이후 **매시 정각**에 자동 실행 (`cron: 0 * * * *`, GitHub은 UTC로 해석)

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
