; rainbow.smt2 — from the lecture slide (UNSAT version)
;
; Variables: rain, rainbow, lightning, doubleRainbow, solution
;
; The formula is UNSAT because:
;   Assertion 1: doubleRainbow - rain - rain = 4
;   Assertion 2: rain * rainbow - lightning = 22
;   Assertion 3: solution = doubleRainbow / 13 - rain
;   Assertion 4: solution = 100   <- BUG! solution forced to 100
;                                    but the math gives solution = -19
;
; Expected repair: change 100 -> -19  (replace_constant)

(declare-const rain          Int)
(declare-const rainbow       Int)
(declare-const lightning     Int)
(declare-const doubleRainbow Int)
(declare-const solution      Int)

; Assertion 1
(assert (= 4 (- (- doubleRainbow rain) rain)))

; Assertion 2
(assert (= 22 (- (* rain rainbow) lightning)))

; Assertion 3
(assert (= solution (- (/ doubleRainbow 13) rain)))

; Assertion 4 - BUG: solution forced to 100 but math gives -19
(assert (= solution 100))
