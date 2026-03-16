; Boolean connective example (Challenge 1 -- replace_boolean strategy)
;
; A simple access control spec: a user gets access if they are
; an admin AND verified. But the rule accidentally uses AND instead of OR
; making it impossible to satisfy along with the other constraints.
;
; Variables:
;   is_admin    -- user has admin role
;   is_verified -- user passed verification
;   is_blocked  -- user is on blocklist
;   has_access  -- result: user gets access
;
; Bug: assertion 3 uses AND but should use OR
; Repair: replace 'and' -> 'or' in (and is_admin is_verified)

(declare-const is_admin    Bool)
(declare-const is_verified Bool)
(declare-const is_blocked  Bool)
(declare-const has_access  Bool)

; Admin is false, verified is true
(assert (= is_admin    false))
(assert (= is_verified true))

; BUG: requires BOTH admin AND verified (too strict -- should be OR)
(assert (= has_access (and is_admin is_verified)))

; User is not blocked
(assert (not is_blocked))

; Access must be granted
(assert has_access)
