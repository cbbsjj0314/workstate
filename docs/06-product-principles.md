# 제품 원칙

## 수동 완전성보다 편의성

WorkState는 단순한 메모를 유지하는 것보다 더 쉬워야 한다.

## 수동 입력보다 자동 수집 우선

관찰 가능한 workflow fact는 integration이 허용하는 범위에서 자동으로 수집해야 한다. manual input은 fallback과 repair를 위한 것이다.

## 추론보다 사실 우선

observed fact와 workflow 해석은 서로 다른 계층이다.

## 투명한 derivation

derived workflow state는 evidence, provenance, confidence, interpretation status를 표시해야 한다.

## 일괄 확인

불확실한 해석은 모든 객관적 event 후가 아니라 workflow boundary 또는 `resume` 시점에 확인해야 한다.

## Local-first storage

WorkState는 기본적으로 workflow 복구 데이터를 local-first 방식으로 유지해야 한다.

## 항상 사용할 수 있는 manual repair

capture가 불완전하거나 잘못된 경우 사용자는 누락된 context, corrective information 또는 override를 추가할 수 있어야 한다.

## Recommendation은 선택 사항

recommendation은 next action을 제안할 수 있지만 객관적 사실이 아니며 사용자 판단을 대체하지 않는다.

## 단순한 메모가 기준이다

WorkState가 단순한 메모, session 다시 읽기 또는 GitHub 직접 확인보다 더 번거롭다면 제품은 실패한 것이다.
