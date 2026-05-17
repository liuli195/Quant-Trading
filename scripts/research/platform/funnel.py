"""Candidate-funnel helpers shared by local research plugins."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CandidateFunnel:
    """Three-stage candidate funnel artifacts."""

    ranked: pd.DataFrame
    discarded: pd.DataFrame
    shortlist: pd.DataFrame
    cloud_candidates: pd.DataFrame


def build_fast_funnel(
    candidates: pd.DataFrame,
    *,
    score_column: str,
    top_k: int,
) -> CandidateFunnel:
    """Rank candidates and keep a first-pass shortlist."""

    ranked = candidates.sort_values([score_column, "candidate_id"], ascending=[False, True]).reset_index(drop=True)
    ranked["fast_rank"] = ranked.index + 1
    shortlist = ranked.head(top_k).copy()
    shortlist["funnel_stage"] = "shortlist"
    discarded = ranked.iloc[top_k:].copy()
    if not discarded.empty:
        discarded["discard_reason"] = "not_in_fast_top_k"
    cloud_candidates = shortlist.head(0).copy()
    return CandidateFunnel(
        ranked=ranked,
        discarded=discarded,
        shortlist=shortlist,
        cloud_candidates=cloud_candidates,
    )


def promote_full_funnel(
    reviewed: pd.DataFrame,
    *,
    cloud_top_k: int,
    eligible_column: str = "eligible_for_cloud",
    score_column: str = "refinement_score",
) -> CandidateFunnel:
    """Promote reviewed shortlist rows to the cloud-candidate stage."""

    ranked = reviewed.sort_values([eligible_column, score_column, "candidate_id"], ascending=[False, False, True]).reset_index(drop=True)
    ranked["full_rank"] = ranked.index + 1
    cloud_candidates = ranked[ranked[eligible_column]].head(cloud_top_k).copy()
    cloud_candidates["funnel_stage"] = "cloud_candidates"
    discarded = ranked[~ranked["candidate_id"].isin(cloud_candidates["candidate_id"])].copy()
    if not discarded.empty:
        discarded["discard_reason"] = discarded.apply(
            lambda row: "failed_local_gates" if not bool(row[eligible_column]) else "not_in_cloud_top_k",
            axis=1,
        )
    return CandidateFunnel(
        ranked=ranked,
        discarded=discarded,
        shortlist=ranked.copy(),
        cloud_candidates=cloud_candidates,
    )
