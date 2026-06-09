# 문제

WorkState는 사용자가 작업을 중단했다가 돌아왔을 때 repository별 workflow 상태를 복구하도록 돕는다.

핵심 resume 질문은 다음과 같다.

> 무엇이 누구의 처리를 기다리고 있는가? (`What is waiting for whom?`)

이 질문의 답은 메모에 반복해서 입력하는 것이 아니라 관찰 가능한 근거에서 도출해야 한다.

## 실제 경쟁 상대

WorkState의 경쟁 상대는 다음과 같다.

- 단순한 메모 유지
- ChatGPT 기록 다시 읽기
- Codex session 다시 열기
- 여러 GitHub 탭 확인
- 작업 내용을 기억에 의존해 관리하기

WorkState가 이러한 대안보다 더 많은 노력을 요구한다면 실패한 것이다.

## 사용자가 복구해야 할 정보

작업을 중단했다가 돌아온 사용자는 다음 정보를 알아야 한다.

- 최근에 발생한 일
- local working tree에서 변경된 내용
- 작업이 commit되거나 push되었는지 여부
- PR이 존재하거나 merge되었는지 여부
- validation 또는 CI가 pending, passed, failed, not observed 중 어떤 상태인지
- AI agent가 아직 실행 중인지 여부
- 마지막으로 작업한 actor
- 누구의 처리가 필요할 가능성이 높은지
- 아직 확인이 필요한 해석
- 제안된 next action이 있다면 그 내용

WorkState는 객관적 사실과 workflow 해석의 구분을 유지해야 한다. 잘못된 해석이 이를 뒷받침한 observed history를 손상해서는 안 된다.

## 제품 기준

WorkState는 단순한 메모보다 더 편리해야 한다. 사용자가 모든 workflow transition 후에 manual checkpoint를 실행하거나, ChatGPT에 상태 기록을 반복해서 요청하거나, integration에서 이미 사용할 수 있는 데이터를 수동으로 다시 입력하도록 요구해서는 안 된다.
