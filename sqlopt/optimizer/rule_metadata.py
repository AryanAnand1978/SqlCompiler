RULE_INFO = {
    "constant_folding": {
        "display_name": "Constant Folding",
        "identity": r"σ_(c ∧ true)(R) = σ_c(R)   — tautology elimination",
    },
    "redundant_filter_elimination": {
        "display_name": "Duplicate Predicate Elimination",
        "identity": "c ∧ c = c",
    },
    "predicate_pushdown": {
        "display_name": "Predicate Pushdown",
        "identity": r"σ_C(R ⋈ S) = σ_C1(R) ⋈ σ_C2(S)   — selection pushdown through join",
    },
    "redundant_join_elimination": {
        "display_name": "Redundant Join Elimination",
        "identity": r"R ⋈_(R.id = S.id) S = R   — redundant self-join pruning",
    },
    "projection_pushdown": {
        "display_name": "Projection Pushdown",
        "identity": r"π_A(σ_c(R)) ⟶ only required columns retained at scan",
    },
}
