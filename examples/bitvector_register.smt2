; BitVector example (Challenge 1 -- replace_bitvector strategy)
;
; A hardware register spec: 8-bit register x must hold a value
; that satisfies a bitmask check and a range constraint.
;
; Bug: the threshold constant 200 is too high -- no 8-bit value
;      can be simultaneously above 200 (unsigned) and equal to 42.
;
; Repair options:
;   replace_bitvector: change constant 200 -> nearby value (e.g. 40)
;   replace_bitvector: change operator bvugt -> bvult

(declare-const x (_ BitVec 8))
(declare-const y (_ BitVec 8))

; x must equal 42
(assert (= x (_ bv42 8)))

; BUG: x must be strictly greater than 200 (impossible if x=42)
(assert (bvugt x (_ bv200 8)))

; y is double x
(assert (= y (bvadd x x)))
