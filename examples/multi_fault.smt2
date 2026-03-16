; Multi-fault example (Challenge 2 -- combine_repairs strategy)
;
; This formula has TWO independent errors.
; No single repair fixes the whole formula -- both must be fixed together.
;
; Scenario: a smart thermostat controller
;   - current_temp must be above min_temp (heating threshold)
;   - target_temp must match the formula: current_temp + adjustment = target_temp
;
; BUG 1: min_temp = 25 is too high (current_temp = 18, so 18 > 25 fails)
;         Fix: min_temp should be <= 17 (e.g. change 25 -> 17)
;
; BUG 2: adjustment = 100 is wrong (18 + 100 = 118 ≠ target_temp = 22)
;         Fix: adjustment should be 4 (18 + 4 = 22)
;
; Fixing BUG 1 alone still leaves BUG 2 (18+100 ≠ 22).
; Fixing BUG 2 alone still leaves BUG 1 (18 > 25 fails).
; Only fixing BOTH makes the formula SAT.

(declare-const current_temp  Int)
(declare-const min_temp      Int)
(declare-const adjustment    Int)
(declare-const target_temp   Int)

; Current temperature reading
(assert (= current_temp 18))

; BUG 1: minimum threshold too high
(assert (= min_temp 25))
(assert (> current_temp min_temp))

; Target temperature calculation
(assert (= target_temp 22))

; BUG 2: adjustment value is wildly wrong
(assert (= adjustment 100))
(assert (= target_temp (+ current_temp adjustment)))
