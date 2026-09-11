PQ Label 1.9.1 설치 안내
========================

지원 환경
- AutoCAD 2027 64-bit
- Windows 64-bit
- 관리자 권한 불필요: 현재 Windows 사용자에게 설치됩니다.

설치
1. AutoCAD를 완전히 종료합니다.
2. Install.cmd를 더블클릭합니다.
3. 설치 성공 메시지를 확인합니다.
4. AutoCAD를 시작하고 PQPALETTE 명령을 실행합니다.

설치 위치
%APPDATA%\Autodesk\ApplicationPlugins\PqLabel.bundle

업데이트
- 기존 PqLabel.bundle은 삭제하지 않고 같은 ApplicationPlugins 폴더에
  PqLabel.bundle.backup-날짜-시간 이름으로 백업됩니다.
- AutoCAD가 실행 중이면 설치를 중단하므로 잠긴 WINDOW/Windows 폴더를
  억지로 지우지 않습니다.

제거
- 배포 ZIP의 Uninstall.cmd 또는 설치 폴더 아래의
  PqLabel.bundle\Installer\Uninstall.cmd를 실행합니다.
- 제거된 Bundle은 복구할 수 있도록
  %LOCALAPPDATA%\PQLabel\Uninstalled 아래로 이동됩니다.

무결성
- 설치기는 PackageContents.xml 버전과 PqLabel.dll SHA-256을 검사합니다.
- 예상 DLL SHA-256:
  9106103A8D46A37631107593B5EC7D610E6B20FDFD5904E12E5D0189B1137018

주요 명령
- PQPALETTE: 관리 창 열기
- PQVALIDATE: XData 및 class/instance 무결성 검사
- PQHELP: 전체 명령 확인
