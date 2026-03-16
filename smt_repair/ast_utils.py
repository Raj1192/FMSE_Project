# Z3 AST traversal and transformation helpers.
# Nothing fancy — DFS collect, node replacement by id, operator swap.

from z3 import (
    is_int_value, is_rational_value,
    is_add, is_sub, is_mul, is_div, is_idiv,
    is_lt, is_le, is_gt, is_ge,
    eq,
)


def is_eq_op(e):
    return e.num_args() >= 2 and e.decl().name() == "="


def get_op_type(e):
    if not e.children():
        return None
    if is_add(e):   return "add"
    if is_sub(e):   return "sub"
    if is_mul(e):   return "mul"
    if is_div(e):   return "div"
    if is_idiv(e):  return "idiv"
    if is_lt(e):    return "lt"
    if is_le(e):    return "le"
    if is_gt(e):    return "gt"
    if is_ge(e):    return "ge"
    if is_eq_op(e): return "eq"
    return None


# Z3 can share sub-expression nodes across the tree, so dedup by id is important
def collect_subexpressions(expr):
    seen = set()
    result = []

    def walk(e):
        eid = e.get_id()
        if eid in seen:
            return
        seen.add(eid)
        result.append(e)
        for child in e.children():
            walk(child)

    walk(expr)
    return result


def collect_numeric_constants(expr):
    return [
        s for s in collect_subexpressions(expr)
        if is_int_value(s) or is_rational_value(s)
    ]


def collect_operator_nodes(expr):
    out = []
    for sub in collect_subexpressions(expr):
        op = get_op_type(sub)
        if op is not None:
            out.append((sub, op))
    return out


def rebuild(expr, new_children):
    return expr.decl()(*new_children)


def transform_expr(expr, transformer):
    # bottom-up walk; transformer returns (new_node, stop_recursing)
    new_expr, stop = transformer(expr)
    if stop:
        return new_expr

    children = expr.children()
    if not children:
        return new_expr

    new_children = [transform_expr(c, transformer) for c in children]

    # nothing changed — return original reference
    if all(eq(o, n) for o, n in zip(children, new_children)):
        return new_expr if not eq(new_expr, expr) else expr

    return rebuild(expr, new_children)


def replace_node_by_id(expr, target_id, replacement):
    """Replace the first node whose .get_id() == target_id."""
    def _t(e):
        if e.get_id() == target_id:
            return replacement, True
        return e, False
    return transform_expr(expr, _t)


def replace_operator_by_id(expr, target_id, new_op):
    """Swap the operator at node target_id with new_op(*children)."""
    def _t(e):
        if e.get_id() == target_id:
            return new_op(*e.children()), True
        return e, False
    return transform_expr(expr, _t)
