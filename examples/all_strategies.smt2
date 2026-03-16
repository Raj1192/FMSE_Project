; all_strategies.smt2
; This example triggers ALL 5 repair strategies at once.
;
; Scenario: A simple smart home system
;   - temperature sensor reads 18 (integer)
;   - heater is ON (boolean)
;   - register value is 42 (bitvector)
;   - All three conflict with their constraints

; ── Integer variables (triggers replace_constant, replace_operator) ──
(declare-const temperature Int)
(declare-const min_temp    Int)

(assert (= temperature 18))
(assert (= min_temp 25))
(assert (> temperature min_temp))   ; BUG: 18 > 25 is false

; ── Boolean variables (triggers replace_boolean) ──
(declare-const heater_on   Bool)
(declare-const system_ok   Bool)

(assert (= heater_on false))
(assert (= system_ok (and heater_on true)))  ; BUG: and should be or
(assert system_ok)
