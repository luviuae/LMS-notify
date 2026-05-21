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

### 1. GitHub 저장소 만들기

이 폴더를 Git 저장소로 만든 뒤 GitHub에 푸시합니다.

```bash
git init
git add .
git commit -m "Add SSU LMS assignment checker"
git branch -M main
git remote add origin https://github.com/<YOUR_USER>/<YOUR_REPO>.git
git push -u origin main
```

### 2. Secrets 등록

GitHub 저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

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
