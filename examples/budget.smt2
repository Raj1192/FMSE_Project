; Mixed example – tests all three repair strategies
; A budget tracking formula with an error.
;
; income = 3000, rent = 1200, food = 800, savings = 500
; The constraint says  income - rent - food = savings,
; but 3000 - 1200 - 800 = 1000  ≠  500.
;
; Possible repairs:
;   - Replace constant 500 with 1000  (replace_constant)
;   - Weaken / delete the equality    (delete_subformula)

(declare-const income  Int)
(declare-const rent    Int)
(declare-const food    Int)
(declare-const savings Int)

(assert (= income 3000))
(assert (= rent   1200))
(assert (= food    800))
(assert (= savings 500))

; This assertion is wrong: 3000 - 1200 - 800 ≠ 500
(assert (= (- income (+ rent food)) savings))
