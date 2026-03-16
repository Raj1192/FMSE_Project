; Simple example: conflicting constant assignments
; x cannot simultaneously equal 5 and 6.
; Repair: change one of the constants (5 or 6).

(declare-const x Int)

(assert (= x 5))
(assert (= x 6))
