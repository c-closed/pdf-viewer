# 가벼운 PDF 뷰어 (Python)

단일 파일 Tkinter PDF 뷰어. 무거운 프레임워크(Qt 등) 없이 매우 가볍습니다.

## 기능
- PDF 열기 (버튼 / 드래그 앤 드롭 / 명령줄 인자)
- **상단 바**: 파일 열기 · 설정 · 검색(찾기/이전/다음·일치 수)
- **하단 컨트롤 바**: 페이지 이동(이전·번호 입력·다음) · 확대/축소 · 폭 맞춤 / 쪽 맞춤 / 회전 · 보기 방식 / 보기 단위
- 열어 놓은 파일명은 창 제목 표시줄에 표시
- **무음 자동 업데이트**: 시작 시 Cloudflare Worker의 최신 버전 manifest를 확인해, 새 버전이 있으면 설치 파일을 받아(sha256 검증) 무음으로 설치 후 앱을 다시 시작 (설정에서 끌 수 있음)
- 버전은 `pdf_viewer.py`의 `__version__` 하나로 관리 (빌드·설치·업데이트 모두 이 값을 사용)
- 보기 방식과 보기 단위를 **따로** 선택 (하단 바)
  - **보기 방식**: **n쪽씩** — 한 행에 가로로 몇 쪽을 배치할지. **숫자 입력칸(스핀박스)** 에 직접 입력 (1~12)
  - **보기 단위**: **페이지**(한 화면씩) / **연속**(스크롤)
  - 두 설정은 독립적이라 **두쪽씩 + 연속 스크롤**, **n쪽씩 + 연속 스크롤** 모두 가능
  - 페이지(또는 한 행)가 창보다 작으면 **가로·세로 가운데 정렬** (모든 조합 공통)
  - **연속**: 행이 창보다 좁으면 가로 가운데, 내용 전체가 창보다 짧으면 세로 가운데 정렬
  - **두쪽씩/n쪽씩**: 여러 쪽을 가로로 나란히, 이전/다음은 한 행(쪽 수)씩 이동 (Shift+휠로 가로 이동)
    - **폭 맞춤**이라도 여러 쪽이 세로로 넘치면 자동으로 창 높이에 맞게 축소 → 행 전체가 보임
- **폭 맞춤 / 쪽 맞춤** 상태에서는 창 크기를 바꾸면 배율도 자동으로 다시 맞춰짐 (창 최대화 포함)
  - **페이지 이동 중에도 유지**: 세로↔가로 등 페이지 방향이 달라지면 새 페이지에 맞게 배율을 자동 재계산 (쪽 맞춤이 계속 유지됨)
- **설정**(상단 '설정' 버튼): 기본 보기 방식 / 기본 보기 단위 / 시작 배율(폭맞춤·쪽맞춤·지정 배율 %), 다음 실행에도 유지 (`%APPDATA%\PDFViewer\settings.json`)
  - 예전 `view_mode` 설정은 자동으로 새 형식으로 마이그레이션됨
  - **PDF 기본 프로그램으로 설정** 버튼: 이 뷰어를 `.pdf` 기본 프로그램으로 등록 (Windows '기본 앱' 설정 화면 바로 열기 지원)
- **텍스트 검색** (문자 단위, 대소문자 무시) — 다음/이전 이동, 일치 영역 하이라이트
- 페이지 이동 (하단 바의 이전·다음·번호 입력, Home/End) — 현재 보기 방식의 쪽 수만큼 이동
- 확대·축소 (하단 바 버튼 / Ctrl+휠), 폭 맞춤 / 쪽 맞춤
- 페이지 회전 (90°씩, 검색 하이라이트도 회전에 정확히 따라감)
- 스크롤: **페이지 단위 = 휠로 페이지 이동**, 연속 단위 = 휠 스크롤, Shift+휠 = 가로 스크롤, 가운데 버튼 드래그 = 팬
- 암호 걸린 PDF 열기

## 키보드 단축키
| 키 | 동작 |
|---|---|
| Ctrl+O | 열기 |
| Ctrl+F | 검색 |
| F3 / Shift+F3 | 다음 / 이전 일치 항목 |
| ←/↑/PageUp | 이전 페이지 |
| →/↓/PageDown/Space | 다음 페이지 |
| Home / End | 처음 / 마지막 페이지 |
| Ctrl + / Ctrl - | 확대 / 축소 |
| Ctrl+0 | 쪽 맞춤 |
| Ctrl+1 | 폭 맞춤 |
| Ctrl+R | 회전 |
| Ctrl+휠 | 확대/축소 |
| Shift+휠 | 가로 스크롤 |

## 요구 사항
- Python 3.10 이상 (검증: 3.12, Windows)
- Tkinter (Windows 공식 설치본 기본 포함)

## 설치
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

배포용 설치 파일은 **사용자 단위**(`%LOCALAPPDATA%\Programs\PDF Viewer`)로 설치되어
관리자 권한(UAC) 없이 무음 자동 업데이트가 가능합니다.
(구 버전 1.1.0의 Program Files 설치본은: 설정 → 앱 → PDF Viewer → 제거 후 새 버전을 설치하세요.)

## 실행
```powershell
.\.venv\Scripts\python.exe pdf_viewer.py            # 빈 창
.\.venv\Scripts\python.exe pdf_viewer.py in.pdf    # 파일 바로 열기
```

## 빌드 (exe + 설치 파일 한 번에)
```powershell
.\build.ps1
# -> dist\PDFViewer\PDFViewer.exe (onedir 폴더, 약 45MB)
# -> installer\PDFViewer-Setup-<버전>.exe (약 47MB, Inno Setup 자동 컴파일)
```
실행 정책 오류가 나면:
```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```
또는
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

빌드는 **onedir(폴더 형태)** 입니다. onefile과 달리 실행 시 임시폴더에 압축을 풀지 않아 **시작이 더 빠릅니다**.
버전은 `pdf_viewer.py`의 `__version__`을 따르며 설치 파일 이름·버전 정보에 자동 반영됩니다.

## 릴리스 / 자동 업데이트 (GitHub + Cloudflare)
**구성**: 소스 = GitHub, 배포 = GitHub Releases + Cloudflare **R2**(설치 파일·manifest), 접점 = Cloudflare **Worker**(`latest.json` 제공).

```
앱 ── GET /latest.json ──▶ Cloudflare Worker ── R2: releases/PDFViewer-Setup-1.2.0.exe, latest.json
     성공 시 새 버전이면 ── GET /download/... (sha256 검증) ──▶ 무음 설치 → 재시작
```

- **릴리스 절차**: `pdf_viewer.py`의 `__version__`을 올리고 태그를 푸시하면 GitHub Actions가 자동으로
  빌드 → GitHub Release 등록 → R2 업로드 → `latest.json` 갱신까지 수행합니다.
  ```powershell
  git tag v1.2.0
  git push origin v1.2.0
  ```
  (로컬 수동 릴리스: `.\tools\publish.ps1`)

- **1회 준비 (Cloudflare)**:
  1. `npx wrangler login`
  2. `npx wrangler r2 bucket create pdf-viewer`
  3. `cd updates-worker; npx wrangler deploy`
  4. 배포 후 표시되는 `https://pdf-viewer-updates.<계정>.workers.dev` 주소를:
     - `pdf_viewer.py`의 `UPDATE_MANIFEST_URL`에 반영
     - GitHub 저장소 변수 `WORKER_BASE_URL`로 등록
  5. GitHub Actions secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
     (권한: `Workers Scripts: Edit`, `Workers R2 Storage: Edit`)

- **환경설정 → 자동 업데이트** 체크 해제로 끌 수 있습니다.

## 아이콘
폴더 안 `icon.ico` 하나로 다음에 자동 적용됩니다 — 앱 창(타이틀바), 실행 파일 `PDFViewer.exe`, 설치 마법사, 제거 프로그램, 시작 메뉴/바탕화면 바로가기.
아이콘을 바꾸려면 `icon.ico`만 교체 후 `.\build.ps1` 실행하세요. (설치 마법사 아이콘은 `Compression=none`에서만 정상 반영됩니다.)

## PDF 기본 프로그램 설정
- **설치 중**: 설치 마법사의 `파일 연결: PDF 파일의 기본 프로그램으로 설정`(기본 체크됨) 항목으로 등록합니다.
- **설치 후**: 앱의 `설정 → PDF 기본 프로그램으로 설정` 버튼으로 언제든 등록/변경할 수 있습니다.
- 등록 내용(사용자 단위, HKCU):
  - ProgID `PDFViewer.pdf` (열기 명령·아이콘)
  - `Applications\PDFViewer.exe` (이름 `PDF Viewer`·아이콘·지원 형식 `.pdf`) → 기본 앱/연결 프로그램 목록에 올바른 이름과 아이콘 표시
  - `.pdf\OpenWithProgids` 등록 → '연결 프로그램' 목록에 표시
  - Capabilities + `RegisteredApplications` → Windows '기본 앱' 목록에 표시
  - 아이콘 경로는 공백 포함 경로를 위해 따옴표로 감쌉 (`"C:\...\PDFViewer.exe",0`)
- Windows 10/11은 기본 앱 변경을 보호하므로, 등록 후 `설정 → 기본 앱`에서 한 번 더 확인해야 할 수 있습니다. (앱에서 그 화면을 바로 열어 줍니다.)
- 제거 시 위 레지스트리 항목은 자동으로 정리됩니다.

## 의존성 (매우 적음)
| 라이브러리 | 용도 | 라이선스 |
|---|---|---|
| pypdfium2 | PDF 렌더링 | Apache-2.0 / BSD-3 |
| Pillow | 이미지 변환 | HPND |
| tkinterdnd2 | 드래그 앤 드롭(선택) | MIT |
