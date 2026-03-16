; Comparison operator example
; x > 10 and x < 5 is UNSAT.
; Repair: change one comparison operator (e.g. > → < or < → >).

(declare-const x Int)
(declare-const y Int)

(assert (> x 10))
(assert (< x 5))
(assert (= y (* x 2)))
